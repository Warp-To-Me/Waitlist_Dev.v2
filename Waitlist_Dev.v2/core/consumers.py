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