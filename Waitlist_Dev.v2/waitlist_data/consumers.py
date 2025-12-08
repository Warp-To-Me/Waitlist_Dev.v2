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
            self.overview_task = asyncio.create_task(self.poll_fleet_overview())

    async def disconnect(self, close_code):
        # Stop background task
        if hasattr(self, 'overview_task'):
            self.overview_task.cancel()

        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # --- PERMISSION HELPER ---
    @sync_to_async
    def check_overview_permission(self, user):
        if user.is_superuser: return True
        allowed = ROLE_HIERARCHY[:10] # Resident and above
        return user.groups.filter(name__in=allowed).exists()

    # --- BACKGROUND LOOP ---
    async def poll_fleet_overview(self):
        """
        Periodically checks ESI for fleet updates.
        Relies on `call_esi` (via get_fleet_composition) to handle caching headers.
        """
        while True:
            try:
                # 1. Get Fleet & FC Context (Sync to Async)
                # We fetch fresh tokens/ids every loop to ensure validity
                fleet_data = await self.get_fleet_context()
                
                if fleet_data and fleet_data['esi_fleet_id']:
                    # 2. Call Service (Now returns composite data)
                    composite_data, _ = await sync_to_async(get_fleet_composition)(
                        fleet_data['esi_fleet_id'], 
                        fleet_data['fc_char']
                    )

                    # 3. Process & Send (Only if data is new/available)
                    if composite_data and composite_data != 'unchanged':
                        summary, hierarchy = await sync_to_async(process_fleet_data)(composite_data)
                        
                        await self.send(text_data=json.dumps({
                            'type': 'fleet_overview',
                            'member_count': len(composite_data.get('members', [])),
                            'summary': summary,
                            'hierarchy': hierarchy
                        }))
                    elif composite_data == 'unchanged':
                        # Optional: Send heartbeat if needed, but silence is fine if frontend has data
                        pass
                else:
                    # 4. ERROR HANDLING: No Fleet ID Found
                    # Send an error state to the frontend so it updates the UI
                    error_msg = "Fleet not linked to ESI"
                    if not fleet_data:
                        error_msg = "FC has no linked character"
                        
                    await self.send(text_data=json.dumps({
                        'type': 'fleet_error',
                        'error': error_msg
                    }))

                # 5. Wait
                # ESI Fleet cache is 5 seconds. We poll slightly slower to be safe.
                await asyncio.sleep(6)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Fleet Poll Error: {e}")
                # Send error to UI
                await self.send(text_data=json.dumps({
                    'type': 'fleet_error',
                    'error': "Connection Error"
                }))
                await asyncio.sleep(10) # Back off on error

    @sync_to_async
    def get_fleet_context(self):
        try:
            fleet = Fleet.objects.get(id=self.fleet_id)
            if not fleet.commander: return None
            
            # Find FC's character for ESI calls
            fc_char = fleet.commander.characters.filter(is_main=True).first()
            if not fc_char:
                fc_char = fleet.commander.characters.first()
            
            if not fc_char: return None

            # Ensure ESI Fleet ID exists
            if not fleet.esi_fleet_id:
                # Try to fetch it if missing
                try:
                    headers = {'Authorization': f'Bearer {fc_char.access_token}'}
                    resp = requests.get(f"{ESI_BASE}/characters/{fc_char.character_id}/fleet/", headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        fleet.esi_fleet_id = data['fleet_id']
                        fleet.save()
                except Exception:
                    pass

            return {'esi_fleet_id': fleet.esi_fleet_id, 'fc_char': fc_char}
        except Fleet.DoesNotExist:
            return None

    # --- STANDARD HANDLERS ---
    async def fleet_update(self, event):
        """ Handles standard waitlist updates (Add/Remove/Move) """
        await self.send(text_data=json.dumps(event))