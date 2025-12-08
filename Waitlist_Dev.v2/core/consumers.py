import asyncio
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.template.loader import render_to_string
from asgiref.sync import sync_to_async
from core.utils import get_system_status

class SystemMonitorConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Authenticate user
        if self.scope["user"].is_anonymous or not self.scope["user"].is_staff:
             # Code 4003: Forbidden/Auth Failed
             await self.close(code=4003)
             return

        await self.accept()
        
        # Start the background task
        self.keep_running = True
        self.task = asyncio.create_task(self.send_status_updates())

    async def disconnect(self, close_code):
        self.keep_running = False
        if hasattr(self, 'task'):
            self.task.cancel()

    async def send_status_updates(self):
        while self.keep_running:
            try:
                # 1. Fetch Data
                context = await sync_to_async(get_system_status)()
                
                # 2. Render HTML Partial
                html = await sync_to_async(render_to_string)('partials/celery_content.html', context)
                
                # 3. Send to Client
                await self.send(text_data=json.dumps({
                    'html': html,
                    'timestamp': context.get('redis_latency', 0)
                }))

                # Wait 1 second (High speed refresh)
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"Monitor Error: {e}")
                # On error, back off slightly to prevent log spam
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