import json
from channels.generic.websocket import AsyncWebsocketConsumer

class FleetConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.fleet_id = self.scope['url_route']['kwargs']['fleet_id']
        self.room_group_name = f'fleet_{self.fleet_id}'

        # Check authentication
        if self.scope["user"].is_anonymous:
            await self.close()
            return

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from group
    async def fleet_update(self, event):
        """
        Handles messages sent from Views via channel_layer.group_send
        Event structure:
        {
            'type': 'fleet_update',
            'action': 'add' | 'remove' | 'move',
            'entry_id': 123,
            'html': '<div>...</div>', (Optional)
            'target_col': 'dps', (Optional)
            'count_update': {'pending': 5, 'dps': 2...} (Optional)
        }
        """
        # Send message to WebSocket
        await self.send(text_data=json.dumps(event))