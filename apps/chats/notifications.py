from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Message
from apps.notifications.services import notify
import json
import base64
import os
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.files.base import ContentFile
from .models import Message
from django.contrib.auth import get_user_model

User = get_user_model()

@receiver(post_save, sender=Message)
def notify_on_admin_message(sender, instance, created, **kwargs):
    if created and instance.sender.is_staff and instance.receiver:
        notify(
            user=instance.receiver,
            title="Новое сообщение",
            message=f"Вы получили новое сообщение от администратора: {instance.text[:50]}..."
        )


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
        file_data = data.get('file')  # base64
        file_name = data.get('filename')
        type_ = data.get('type', 'text')

        receiver = await database_sync_to_async(User.objects.get)(id=receiver_id)

        file = None
        if file_data and file_name:
            format, b64data = file_data.split(';base64,')
            file = ContentFile(base64.b64decode(b64data), name=file_name)

        message = await database_sync_to_async(Message.objects.create)(
            sender=self.user,
            receiver=receiver,
            text=text,
            type=type_,
            file=file
        )

        payload = {
            'id': message.id,
            'sender': self.user.id,
            'receiver': receiver.id,
            'text': text,
            'file': message.file.url if message.file else None,
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
