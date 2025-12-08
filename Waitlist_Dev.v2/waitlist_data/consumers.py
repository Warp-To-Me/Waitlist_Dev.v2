import json
import asyncio
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.utils import timezone

# Local Imports
from waitlist_data.models import Fleet
from pilot_data.models import EveCharacter, EsiHeaderCache
from core.utils import ROLE_HIERARCHY
from esi_calls.fleet_service import get_fleet_composition, process_fleet_data, ESI_BASE
from esi_calls.token_manager import check_token
import requests

logger = logging.getLogger(__name__)

class FleetConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.fleet_id = self.scope['url_route']['kwargs']['fleet_id']
        self.room_group_name = f'fleet_{self.fleet_id}'
        self.user = self.scope["user"]

        # Check authentication
        if self.user.is_anonymous:
            await self.close()
            return

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # Permissions Check for Fleet Overview
        # We start the background task ONLY if the user is Resident+
        if await self.check_overview_permission(self.user):
            # NEW: Only start polling if the user is the Fleet Commander
            if await self.check_is_commander(self.user):
                self.overview_task = asyncio.create_task(self.poll_fleet_overview())

    async def disconnect(self, close_code):
        # Stop background task
        if hasattr(self, 'overview_task'):
            self.overview_task.cancel()
            try:
                await self.overview_task
            except asyncio.CancelledError:
                pass

        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # --- PERMISSION HELPER ---
    @sync_to_async
    def check_overview_permission(self, user):
        if user.is_superuser: return True
        # Using capability check to match views
        return user.groups.filter(capabilities__slug='view_fleet_overview').exists()

    @sync_to_async
    def check_is_commander(self, user):
        """
        Checks if the current user is the designated commander of this specific fleet.
        """
        try:
            fleet = Fleet.objects.get(id=self.fleet_id)
            return fleet.commander == user
        except Fleet.DoesNotExist:
            return False

    # --- BACKGROUND LOOP ---
    async def poll_fleet_overview(self):
        """
        Periodically checks ESI for fleet updates.
        Cached in fleet_service to prevent spam.
        """
        while True:
            try:
                # 1. Get Fleet & FC Context (Sync to Async)
                # We fetch fresh tokens/ids every loop to ensure validity
                fleet_data = await self.get_fleet_context()
                
                # FIX: Use .get() to avoid KeyError if fleet_data contains an error message
                if fleet_data and fleet_data.get('esi_fleet_id'):
                    # 2. Call Service (Cached internally)
                    # Note: get_fleet_composition returns (data, error_string)
                    # We need to handle the potential for error_string being returned
                    # The fleet_service.py get_fleet_composition might return (None, error_msg) on failure
                    
                    # Assuming get_fleet_composition signature is (fleet_id, fc_character)
                    # and returns (data, error) tuple based on typical patterns in this project
                    
                    result = await sync_to_async(get_fleet_composition)(
                        fleet_data['esi_fleet_id'], 
                        fleet_data['fc_char']
                    )
                    
                    # Unpack result safely
                    composite_data = None
                    error = None
                    
                    if isinstance(result, tuple):
                        composite_data, error = result
                    else:
                        # Fallback if signature is different (e.g. just returns data)
                        composite_data = result

                    # 3. Process & Send (Only if data is new/available)
                    if composite_data and composite_data != 'unchanged':
                        summary, hierarchy = await sync_to_async(process_fleet_data)(composite_data)
                        
                        await self.send(text_data=json.dumps({
                            'type': 'fleet_overview',
                            'member_count': len(composite_data.get('members', [])),
                            'summary': summary,
                            'hierarchy': hierarchy
                        }))
                    elif error:
                        # 404 handling logic: Invalidate ID if fleet not found
                        if "404" in str(error):
                            logger.warning(f"Fleet {self.fleet_id} returned 404. Invalidating ESI ID.")
                            await self.invalidate_fleet_id(self.fleet_id)
                            await self.send(text_data=json.dumps({
                                'type': 'fleet_error',
                                'error': "Fleet not found. Attempting to relink..."
                            }))
                        else:
                            # Other errors (500, etc) - log but don't crash loop
                            logger.warning(f"Fleet poll error: {error}")
                            pass
                    elif composite_data == 'unchanged':
                        pass
                else:
                    # 4. ERROR HANDLING: No Fleet ID Found or Context Error
                    error_msg = "Fleet not linked to ESI"
                    if not fleet_data:
                        error_msg = "FC has no linked character"
                    elif isinstance(fleet_data, dict) and fleet_data.get('error'):
                        error_msg = fleet_data['error']
                        
                    await self.send(text_data=json.dumps({
                        'type': 'fleet_error',
                        'error': error_msg
                    }))

                # 5. Wait
                # Service caches for 10s, so we poll at 10s to match
                await asyncio.sleep(10)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Fleet Poll Error: {e}")
                # Send error to UI
                try:
                    await self.send(text_data=json.dumps({
                        'type': 'fleet_error',
                        'error': "Connection Error"
                    }))
                except Exception:
                    pass # Connection might be already closed
                await asyncio.sleep(10) # Back off on error

    @sync_to_async
    def get_fleet_context(self):
        try:
            fleet = Fleet.objects.get(id=self.fleet_id)
            if not fleet.commander: return {'error': 'No Commander'}
            
            # Find FC's character for ESI calls
            fc_char = fleet.commander.characters.filter(is_main=True).first()
            if not fc_char:
                fc_char = fleet.commander.characters.first()
            
            if not fc_char: return {'error': 'FC has no characters'}

            # --- CRITICAL FIX: Ensure Token is Valid ---
            # This refreshes the FC's token if needed, preventing "FC must refresh page" issue
            if not check_token(fc_char):
                return {'error': 'FC Token Invalid / Expired'}

            # Ensure ESI Fleet ID exists
            if not fleet.esi_fleet_id:
                # Try to fetch it if missing
                try:
                    headers = {'Authorization': f'Bearer {fc_char.access_token}'}
                    # Added timeout to prevent hanging
                    resp = requests.get(f"{ESI_BASE}/characters/{fc_char.character_id}/fleet/", headers=headers, timeout=5)
                    if resp.status_code == 200:
                        data = resp.json()
                        fleet.esi_fleet_id = data['fleet_id']
                        fleet.save()
                except Exception:
                    pass

            return {'esi_fleet_id': fleet.esi_fleet_id, 'fc_char': fc_char}
        except Fleet.DoesNotExist:
            return None

    @sync_to_async
    def invalidate_fleet_id(self, fleet_db_id):
        """
        Clears the stored ESI ID if it's dead (404), forcing a re-scan.
        """
        try:
            fleet = Fleet.objects.get(id=fleet_db_id)
            fleet.esi_fleet_id = None
            fleet.save()
        except Fleet.DoesNotExist:
            pass

    # --- STANDARD HANDLERS ---
    async def fleet_update(self, event):
        """ Handles standard waitlist updates (Add/Remove/Move) """
        await self.send(text_data=json.dumps(event))