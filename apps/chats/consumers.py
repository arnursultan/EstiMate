import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import Message, ChatRoom
from apps.users.models import User

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_id = self.scope["url_route"]["kwargs"]["chat_id"]
        self.room_group_name = f"chat_{self.chat_id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data["message"]
        sender_id = data["sender_id"]

        chat = await ChatRoom.objects.aget(id=self.chat_id)
        sender = await User.objects.aget(id=sender_id)
        new_message = await Message.objects.acreate(chat=chat, sender=sender, content=message)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message,
                "sender": sender.first_name,
                "created_at": str(new_message.created_at),
            },
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))
