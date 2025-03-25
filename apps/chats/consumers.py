import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Message
from django.contrib.auth import get_user_model

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if self.user.is_anonymous:
            await self.close()
        else:
            self.room_group_name = f'user_{self.user.id}'
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        receiver_id = data['receiver']
        text = data.get('text')
        type_ = data.get('type', 'text')

        receiver = await database_sync_to_async(User.objects.get)(id=receiver_id)

        message = await database_sync_to_async(Message.objects.create)(
            sender=self.user,
            receiver=receiver,
            text=text,
            type=type_,
        )

        payload = {
            'id': message.id,
            'sender': self.user.id,
            'receiver': receiver.id,
            'text': text,
            'type': type_,
            'timestamp': str(message.timestamp),
        }

        await self.channel_layer.group_send(
            f'user_{receiver.id}',
            {
                'type': 'chat.message',
                'message': payload,
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event['message']))
