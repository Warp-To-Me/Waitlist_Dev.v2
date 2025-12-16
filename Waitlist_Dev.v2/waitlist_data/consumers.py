import json
import asyncio
import logging
import uuid
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async, async_to_sync
from django.utils import timezone
from django.core.cache import cache

# Local Imports
from waitlist_data.models import Fleet, FleetActivity, WaitlistEntry, CharacterStats # Added CharacterStats
from pilot_data.models import EveCharacter, EsiHeaderCache, ItemType
from core.utils import ROLE_HIERARCHY
from esi_calls.fleet_service import get_fleet_composition, process_fleet_data, resolve_unknown_names, ESI_BASE
from esi_calls.token_manager import check_token
import requests

logger = logging.getLogger(__name__)

class FleetConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.token = self.scope['url_route']['kwargs']['token']
        self.room_group_name = f'fleet_{self.token}'
        self.user = self.scope["user"]
        
        # Get client IP from scope headers
        headers = dict(self.scope.get('headers', []))
        if b'x-forwarded-for' in headers:
            self.client_ip = headers[b'x-forwarded-for'].decode('utf-8').split(',')[0].strip()
        else:
            self.client_ip = self.scope.get('client', ['unknown'])[0]

        if self.user.is_anonymous:
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        if await self.check_overview_permission(self.user):
            self.overview_task = asyncio.create_task(self.poll_fleet_overview())

    async def disconnect(self, close_code):
        if hasattr(self, 'overview_task'):
            self.overview_task.cancel()

        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    @sync_to_async
    def check_overview_permission(self, user):
        if user.is_superuser: return True
        return user.groups.filter(capabilities__slug='view_fleet_overview').exists()

    async def poll_fleet_overview(self):
        """
        Periodically checks ESI for fleet updates and LOGS NEW DETECTIONS.
        """
        while True:
            try:
                fleet_data = await self.get_fleet_context()
                
                if fleet_data and fleet_data.get('esi_fleet_id'):
                    result = await sync_to_async(get_fleet_composition)(
                        fleet_data['esi_fleet_id'], 
                        fleet_data['fc_char']
                    )
                    
                    composite_data = None
                    error = None
                    
                    if isinstance(result, tuple): composite_data, error = result
                    else: composite_data = result

                    if composite_data and composite_data != 'unchanged':
                        # 1. Resolve External Names (for non-DB members)
                        all_ids = [m['character_id'] for m in composite_data.get('members', [])]
                        resolved_names = await sync_to_async(resolve_unknown_names)(all_ids)

                        # 2. Audit Logic (Pass names to avoid re-fetch)
                        await self.audit_fleet_members(self.token, composite_data, resolved_names)

                        # 3. Process Data for UI (Inject resolved names)
                        summary, hierarchy = await sync_to_async(process_fleet_data)(composite_data, resolved_names)
                        
                        await self.send(text_data=json.dumps({
                            'type': 'fleet_overview',
                            'member_count': len(composite_data.get('members', [])),
                            'summary': summary,
                            'hierarchy': hierarchy
                        }))
                    elif error:
                        if "404" in str(error):
                            await self.invalidate_fleet_id(self.token)
                            await self.send(text_data=json.dumps({
                                'type': 'fleet_error',
                                'error': "Fleet not found. Attempting to relink..."
                            }))
                        else:
                            pass
                else:
                    error_msg = "Fleet not linked to ESI"
                    if not fleet_data: error_msg = "FC has no linked character"
                    elif isinstance(fleet_data, dict) and fleet_data.get('error'): error_msg = fleet_data['error']
                    await self.send(text_data=json.dumps({
                        'type': 'fleet_error',
                        'error': error_msg
                    }))

                await asyncio.sleep(5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Fleet Poll Error (IP: {getattr(self, 'client_ip', 'Unknown')}): {e}")
                await asyncio.sleep(5)

    @sync_to_async
    def get_fleet_context(self):
        try:
            # Try parsing as UUID first (standard join_token)
            is_uuid = False
            try:
                uuid.UUID(str(self.token))
                is_uuid = True
            except ValueError:
                pass
            
            fleet = None
            if is_uuid:
                try:
                    fleet = Fleet.objects.get(join_token=self.token)
                except Fleet.DoesNotExist:
                    pass

            # Fallback to legacy ID
            if not fleet:
                try:
                    fleet = Fleet.objects.get(id=self.token)
                except (Fleet.DoesNotExist, ValueError):
                    return None

            if not fleet.commander: return {'error': 'No Commander'}
            fc_char = fleet.commander.characters.filter(is_main=True).first()
            if not fc_char: fc_char = fleet.commander.characters.first()
            if not fc_char: return {'error': 'FC has no characters'}
            if not check_token(fc_char): return {'error': 'FC Token Invalid / Expired'}
            if not fleet.esi_fleet_id:
                try:
                    headers = {'Authorization': f'Bearer {fc_char.access_token}'}
                    resp = requests.get(f"{ESI_BASE}/characters/{fc_char.character_id}/fleet/", headers=headers, timeout=5)
                    if resp.status_code == 200:
                        data = resp.json()
                        fleet.esi_fleet_id = data['fleet_id']
                        fleet.save()
                except Exception: pass
            return {'esi_fleet_id': fleet.esi_fleet_id, 'fc_char': fc_char}
        except Exception as e:
            return {'error': str(e)}

    @sync_to_async
    def invalidate_fleet_id(self, token):
        try:
            # Try parsing as UUID first (standard join_token)
            is_uuid = False
            try:
                uuid.UUID(str(token))
                is_uuid = True
            except ValueError:
                pass

            if is_uuid:
                fleet = Fleet.objects.get(join_token=token)
            else:
                fleet = Fleet.objects.get(id=token)
                
            fleet.esi_fleet_id = None
            fleet.save()
        except (Fleet.DoesNotExist, ValueError): pass

    @sync_to_async
    def audit_fleet_members(self, token, composite_data, resolved_names):
        """
        Compares current ESI state against cached snapshot.
        RUNS SYNCHRONOUSLY inside a thread via @sync_to_async.
        """
        members = composite_data.get('members', [])
        wings_structure = composite_data.get('wings', [])
        
        if not members: return

        # --- NEW: Build ID -> Name Map for Wings/Squads ---
        structure_map = {}
        for w in wings_structure:
            structure_map[w['id']] = w['name'] 
            for s in w.get('squads', []):
                structure_map[s['id']] = s['name'] 

        def get_pos_name(wing_id, squad_id):
            w_name = structure_map.get(wing_id, f"Wing {wing_id}")
            s_name = structure_map.get(squad_id, f"Squad {squad_id}")
            if wing_id <= 0: return "Fleet Command"
            if squad_id <= 0: return w_name
            return f"{w_name} / {s_name}"

        # 1. Build Current State Map
        current_state = {}
        for m in members:
            current_state[m['character_id']] = {
                'role': m['role'],
                'wing_id': m['wing_id'],
                'squad_id': m['squad_id'],
                'ship_type_id': m['ship_type_id']
            }

        # 2. Retrieve Previous State from Cache
        cache_key = f"fleet_audit_snapshot_{token}"
        previous_state = cache.get(cache_key)

        # 3. Save Current as New Snapshot
        cache.set(cache_key, current_state, timeout=86400)

        # --- ANALYSIS ---
        previous_ids = set(previous_state.keys()) if previous_state else set()
        current_ids = set(current_state.keys())

        joined_ids = current_ids - previous_ids
        left_ids = previous_ids - current_ids
        common_ids = current_ids.intersection(previous_ids)

        if not joined_ids and not left_ids and not common_ids: return

        all_relevant_ids = list(joined_ids | left_ids | common_ids)
        known_chars = EveCharacter.objects.filter(character_id__in=all_relevant_ids).in_bulk(field_name='character_id')
        
        fleet = Fleet.objects.get(join_token=token)
        new_logs = []
        
        needed_ship_ids = set(m['ship_type_id'] for m in members if m['character_id'] in all_relevant_ids)
        ship_map = ItemType.objects.filter(type_id__in=needed_ship_ids).in_bulk(field_name='type_id')

        def get_char_and_ship(cid):
            char = known_chars.get(cid)
            if not char: return None, None, None

            state_source = current_state if cid in current_state else previous_state
            ship_id = state_source[cid]['ship_type_id']
            ship_name = "Unknown Ship"
            if ship_id in ship_map:
                ship_name = ship_map[ship_id].type_name
                
            return char, ship_id, ship_name

        # --- Helper for Stats Update ---
        def update_char_stats(character, event_type, ship_name, timestamp):
            """
            Optimized stats updater.
            event_type: 'join', 'leave', 'reship'
            """
            stats, _ = CharacterStats.objects.get_or_create(character=character)
            
            if event_type == 'join':
                # Start new session
                # If there was a previous open session, close it first (safety)
                if stats.active_session_start:
                    diff = (timestamp - stats.active_session_start).total_seconds()
                    if 0 < diff < 86400:
                        stats.total_seconds += int(diff)
                        h_name = stats.active_hull or "Unknown"
                        stats.hull_stats[h_name] = stats.hull_stats.get(h_name, 0) + int(diff)
                
                stats.active_session_start = timestamp
                stats.active_hull = ship_name
                stats.save()

            elif event_type == 'leave':
                # Close session
                if stats.active_session_start:
                    diff = (timestamp - stats.active_session_start).total_seconds()
                    if diff > 0:
                        stats.total_seconds += int(diff)
                        h_name = stats.active_hull or "Unknown"
                        stats.hull_stats[h_name] = stats.hull_stats.get(h_name, 0) + int(diff)
                    
                    stats.active_session_start = None
                    stats.active_hull = None
                    stats.save()

            elif event_type == 'reship':
                # Close current leg, start new leg
                if stats.active_session_start:
                    diff = (timestamp - stats.active_session_start).total_seconds()
                    if diff > 0:
                        stats.total_seconds += int(diff)
                        h_name = stats.active_hull or "Unknown"
                        stats.hull_stats[h_name] = stats.hull_stats.get(h_name, 0) + int(diff)
                
                stats.active_session_start = timestamp
                stats.active_hull = ship_name
                stats.save()

        now = timezone.now()

        # A. HANDLE JOINS
        for cid in joined_ids:
            char, sid, sname = get_char_and_ship(cid)
            if not char: continue

            # Update Stats Model
            update_char_stats(char, 'join', sname, now)

            # Waitlist Logic
            wl_entries = WaitlistEntry.objects.filter(fleet=fleet, character=char)
            details = "Manual Join (In-Game)"
            action = 'esi_join'

            if wl_entries.exists():
                details = "Joined Fleet (Waitlist Cleared)"
                for entry in wl_entries:
                    async_to_sync(self.channel_layer.group_send)(
                        self.room_group_name,
                        {
                            'type': 'fleet_update',
                            'action': 'remove',
                            'entry_id': entry.id
                        }
                    )
                    entry.delete()
            else:
                has_history = FleetActivity.objects.filter(fleet=fleet, character=char).exists()
                if has_history: details = "Arrived in Fleet"
            
            new_logs.append(FleetActivity(
                fleet=fleet, character=char, action=action,
                ship_name=sname, hull_id=sid, details=details
            ))

        # B. HANDLE LEAVES
        if previous_state: 
            for cid in left_ids:
                char, sid, sname = get_char_and_ship(cid)
                if not char: continue
                
                # Update Stats Model
                update_char_stats(char, 'leave', sname, now)
                
                new_logs.append(FleetActivity(
                    fleet=fleet, character=char, action='left_fleet',
                    ship_name=sname, hull_id=sid, details="Detected departure via ESI"
                ))

        # C. HANDLE MOVES & CHANGES
        if previous_state:
            for cid in common_ids:
                char, sid, sname = get_char_and_ship(cid)
                if not char: continue
                
                old = previous_state[cid]
                new = current_state[cid]
                
                # 1. Ship Change
                if old['ship_type_id'] != new['ship_type_id']:
                    old_ship_name = "Unknown"
                    if old['ship_type_id'] in ship_map: old_ship_name = ship_map[old['ship_type_id']].type_name
                    
                    # Update Stats Model
                    update_char_stats(char, 'reship', sname, now)
                    
                    details = f"Reshipped: {old_ship_name} -> {sname}"
                    new_logs.append(FleetActivity(
                        fleet=fleet, character=char, action='ship_change',
                        ship_name=sname, hull_id=sid, details=details
                    ))

                # 2. Position Change
                if old['wing_id'] != new['wing_id'] or old['squad_id'] != new['squad_id']:
                    old_pos = get_pos_name(old['wing_id'], old['squad_id'])
                    new_pos = get_pos_name(new['wing_id'], new['squad_id'])
                    details = f"Moved: {old_pos} -> {new_pos}"
                    new_logs.append(FleetActivity(
                        fleet=fleet, character=char, action='moved',
                        ship_name=sname, hull_id=sid, details=details
                    ))
                
                # 3. Role Change
                if old['role'] != new['role']:
                    act = 'promoted'
                    if 'commander' in new['role'] and 'commander' not in old['role']: act = 'promoted'
                    elif 'member' in new['role'] and 'commander' in old['role']: act = 'demoted'
                    else: act = 'promoted'
                    
                    clean_old = old['role'].replace('fleet_', '').replace('wing_', '').replace('squad_', '').title()
                    clean_new = new['role'].replace('fleet_', '').replace('wing_', '').replace('squad_', '').title()
                    details = f"{clean_old} -> {clean_new}"
                    new_logs.append(FleetActivity(
                        fleet=fleet, character=char, action=act,
                        ship_name=sname, hull_id=sid, details=details
                    ))

        if new_logs:
            FleetActivity.objects.bulk_create(new_logs)

    async def fleet_update(self, event):
        await self.send(text_data=json.dumps(event))