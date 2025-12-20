import asyncio
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.template.loader import render_to_string
from django.core.serializers.json import DjangoJSONEncoder
from asgiref.sync import sync_to_async
from core.utils import get_system_status
from core.script_manager import ScriptManager

class SystemMonitorConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Authenticate user
        if self.scope["user"].is_anonymous or not self.scope["user"].is_staff:
             # Code 4003: Forbidden/Auth Failed
             await self.close(code=4003)
             return

        await self.accept()
        
        # Join system broadcast group
        await self.channel_layer.group_add("system", self.channel_name)

        # Start the background task
        self.keep_running = True
        self.task = asyncio.create_task(self.send_status_updates())

    async def disconnect(self, close_code):
        self.keep_running = False
        if hasattr(self, 'task'):
            self.task.cancel()
        
        await self.channel_layer.group_discard("system", self.channel_name)

    async def celery_task_update(self, event):
        """
        Relay Celery events to the frontend.
        """
        await self.send(text_data=json.dumps(event['data']))

    async def send_status_updates(self):
        while self.keep_running:
            try:
                # 1. Fetch Data
                context = await sync_to_async(get_system_status)()
                
                # 2. Send to Client (JSON)
                await self.send(text_data=json.dumps(context, cls=DjangoJSONEncoder))

                # Wait 1 second (High speed refresh)
                await asyncio.sleep(1)
            
            except asyncio.CancelledError:
                # Break the loop immediately if cancelled
                break
                
            except Exception as e:
                print(f"Monitor Error: {e}")
                # On error, back off slightly to prevent log spam
                # Check running state before sleeping to allow faster shutdown
                if self.keep_running:
                    await asyncio.sleep(5)

class UserConsumer(AsyncWebsocketConsumer):
    """
    Handles personal notifications for a specific logged-in user.
    Used for: ESI Rate Limit monitoring, Personal Alerts, etc.
    """
    async def connect(self):
        self.user = self.scope["user"]
        
        if self.user.is_anonymous:
            await self.close()
            return

        # Join unique user group
        self.group_name = f"user_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def user_notification(self, event):
        """
        Standard handler to push data down the socket.
        Expects event['data'] to be a dictionary.
        """
        await self.send(text_data=json.dumps(event['data']))

class ScriptConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.script_id = self.scope['url_route']['kwargs']['script_id']
        
        # Check permissions
        # 'access_admin' is required. Using sync_to_async to check capability/group
        if not await self.check_permission():
            await self.close(code=4003)
            return

        self.group_name = f"script_{self.script_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send history
        await self.send_history()

    @sync_to_async
    def check_permission(self):
        # Must be superuser or have access_admin capability
        if self.user.is_superuser: 
            return True
        from core.utils import SYSTEM_CAPABILITIES, get_user_highest_role
        
        # Check explicit capability assignment via Roles
        # Simplified check: just check superuser or manual role mapping for now
        # Actually we have a helper in auth slice on frontend, but here we need backend check.
        # The 'access_admin' capability is mapped to 'Admin' role in core/utils.py
        
        # Let's just reuse the logic if possible or check is_staff for now as baseline
        if not self.user.is_staff:
            return False
            
        # Proper check:
        # TODO: Import capability check logic properly if needed.
        # For now, restriction to Superuser or Admin/Leadership group is safest.
        if self.user.groups.filter(name__in=['Admin', 'Leadership']).exists():
            return True
            
        return False

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def send_history(self):
        # Fetch logs from ScriptManager (Sync)
        logs = await sync_to_async(ScriptManager.get_script_logs)(self.script_id)
        if logs:
            for line in logs:
                await self.send(text_data=json.dumps({
                    'type': 'log',
                    'message': line
                }))

    async def log_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'log',
            'message': event['message']
        }))

    async def status_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'status',
            'status': event['status']
        }))
