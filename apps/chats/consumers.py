import json
import base64
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.files.base import ContentFile
from .models import Message
import logging

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """Обработка подключения WebSocket"""
        self.user = self.scope['user']

        if self.user.is_anonymous:
            # Анонимные пользователи не могут подключаться к чату
            await self.close()
        else:
            self.room_group_name = f'user_{self.user.id}'
            # Присоединиться к группе
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()

            # Отправляем сообщение о подключении
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': 'Подключение установлено'
            }))

    async def disconnect(self, close_code):
        """Обработка отключения WebSocket"""
        if hasattr(self, 'room_group_name'):
            # Покидаем группу
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        """Обработка входящего сообщения от клиента"""
        try:
            data = json.loads(text_data)
            receiver_id = data.get('receiver')
            text = data.get('text')
            file_data = data.get('file')  # base64-кодированный файл
            file_name = data.get('filename')
            type_ = data.get('type', 'text')

            # Проверка типа сообщения
            if type_ not in [choice[0] for choice in Message.TYPE_CHOICES]:
                await self.send(text_data=json.dumps({
                    'error': f"Недопустимый тип сообщения: {type_}"
                }))
                return

            # Проверка получателя
            try:
                receiver = await self.get_user(receiver_id)

                # Проверка, что партнер может отправлять сообщения только админам
                if not self.user.is_staff and not receiver.is_staff:
                    await self.send(text_data=json.dumps({
                        'error': "Партнеры могут отправлять сообщения только администраторам"
                    }))
                    return
            except Exception as e:
                await self.send(text_data=json.dumps({
                    'error': f"Получатель не найден: {str(e)}"
                }))
                return

            # Обработка файла, если есть
            file = None
            if file_data and file_name:
                try:
                    format, b64data = file_data.split(';base64,')
                    file = ContentFile(base64.b64decode(b64data), name=file_name)
                except Exception as e:
                    await self.send(text_data=json.dumps({
                        'error': f"Ошибка при обработке файла: {str(e)}"
                    }))
                    return

            # Создание сообщения
            message = await self.create_message(
                sender=self.user,
                receiver=receiver,
                text=text,
                type=type_,
                file=file
            )

            # Подготовка данных для отправки
            payload = {
                'id': message.id,
                'sender': self.user.id,
                'sender_name': f"{self.user.first_name} {self.user.last_name}",
                'receiver': receiver.id,
                'text': text,
                'file': message.file.url if message.file else None,
                'type': type_,
                'timestamp': str(message.timestamp),
                'is_read': message.is_read,
            }

            # Отправка сообщения получателю
            await self.channel_layer.group_send(
                f'user_{receiver.id}',
                {
                    'type': 'chat.message',
                    'message': payload,
                }
            )

            # Отправка подтверждения отправителю
            await self.send(text_data=json.dumps({
                'type': 'message_sent',
                'message': payload
            }))

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'error': "Некорректный формат данных"
            }))
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения: {str(e)}")
            await self.send(text_data=json.dumps({
                'error': f"Произошла ошибка: {str(e)}"
            }))

    async def chat_message(self, event):
        """Отправка сообщения клиенту"""
        await self.send(text_data=json.dumps(event['message']))

    @database_sync_to_async
    def get_user(self, user_id):
        """Получение пользователя из базы данных"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.get(id=user_id)

    @database_sync_to_async
    def create_message(self, sender, receiver, text, type, file=None):
        """Создание сообщения в базе данных"""
        message = Message.objects.create(
            sender=sender,
            receiver=receiver,
            text=text,
            type=type,
            file=file
        )
        return message