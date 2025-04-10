import json
import logging
import base64
import uuid
import os
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.conf import settings
from .models import Chat, Message

logger = logging.getLogger(__name__)
User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket потребитель для обработки сообщений чата в реальном времени.

    Обеспечивает следующую функциональность:
    - Установка соединения с проверкой доступа к чату
    - Обработка входящих сообщений (текстовых и файловых)
    - Рассылка сообщений участникам чата
    """

    async def connect(self):
        """Установка WebSocket соединения с проверкой доступа."""
        self.user = self.scope['user']

        # Проверка аутентификации пользователя
        if not self.user.is_authenticated:
            logger.warning(f"Попытка неавторизованного доступа к WebSocket")
            await self.close()
            return

        # Получаем ID чата из URL
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        self.chat_group_name = f'chat_{self.chat_id}'

        # Проверка доступа пользователя к чату
        if not await self.user_has_chat_access(self.user, self.chat_id):
            logger.warning(f"Пользователь {self.user.id} пытается получить доступ к чату {self.chat_id} без прав")
            await self.close()
            return

        # Присоединяемся к группе чата
        await self.channel_layer.group_add(
            self.chat_group_name,
            self.channel_name
        )

        await self.accept()
        logger.info(f"Пользователь {self.user.id} присоединился к чату {self.chat_id}")

    async def disconnect(self, close_code):
        """Обработка отключения от WebSocket."""
        # Покидаем группу чата
        await self.channel_layer.group_discard(
            self.chat_group_name,
            self.channel_name
        )
        logger.info(f"Пользователь {self.user.id} отключился от чата {self.chat_id}")

    async def receive(self, text_data):
        """Обработка входящих сообщений от WebSocket."""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type', 'text')
            content = text_data_json.get('message', '')
            file_data = text_data_json.get('file', None)
            file_name = text_data_json.get('file_name', None)

            # Проверка валидности данных
            if message_type not in ['text', 'image', 'video', 'document']:
                logger.warning(f"Получен неизвестный тип сообщения: {message_type}")
                await self.send(text_data=json.dumps({
                    'error': 'Неизвестный тип сообщения'
                }))
                return

            # Проверка наличия обязательных данных
            if message_type == 'text' and not content:
                logger.warning(f"Получено пустое текстовое сообщение")
                await self.send(text_data=json.dumps({
                    'error': 'Текстовое сообщение не может быть пустым'
                }))
                return

            if message_type in ['image', 'video', 'document'] and not file_data:
                logger.warning(f"Получено сообщение с файлом без данных файла")
                await self.send(text_data=json.dumps({
                    'error': f'Сообщение типа {message_type} должно содержать файл'
                }))
                return

            # Дополнительная проверка для партнеров - могут общаться только с админами
            if self.user.role == 'partner':
                chat = await database_sync_to_async(Chat.objects.get)(id=self.chat_id)
                admin = await database_sync_to_async(lambda: chat.admin)()

                if admin.role != 'admin':
                    logger.warning(
                        f"Партнер {self.user.id} пытается отправить сообщение в чат {self.chat_id}, который не с администратором")
                    await self.send(text_data=json.dumps({
                        'error': 'Партнеры могут общаться только с администраторами'
                    }))
                    return

            # Создаем сообщение в базе данных
            message = await self.save_message(message_type, content, file_data, file_name)

            # Получаем URL файла, если он был сохранен
            file_url = None
            actual_file_name = file_name or (message.file.name.split('/')[-1] if message.file else None)

            if message.file:
                from django.conf import settings
                file_url = message.file.url
                # Добавляем полный URL
                if hasattr(settings, 'BASE_URL') and not file_url.startswith(('http://', 'https://')):
                    file_url = f"{settings.BASE_URL}{file_url}"

            # Добавляем прямой URL для доступа к файлу через API
            direct_file_url = None
            if message.file:
                from django.urls import reverse
                api_url = reverse('chat:message-file', kwargs={'message_id': message.id})
                if hasattr(settings, 'BASE_URL'):
                    direct_file_url = f"{settings.BASE_URL}{api_url}"

            # Добавляем тип файла в сообщение для клиента
            file_type = message.file_type if message.file else None

            # Отправляем сообщение всем участникам чата
            await self.channel_layer.group_send(
                self.chat_group_name,
                {
                    'type': 'chat_message',
                    'message': {
                        'id': message.id,
                        'sender_id': message.sender.id,
                        'sender_name': f"{message.sender.first_name} {message.sender.last_name}",
                        'sender_role': message.sender.role,
                        'content': message.content,
                        'file_url': file_url,
                        'direct_file_url': direct_file_url,
                        'file_name': actual_file_name,
                        'file_type': file_type,  # Добавляем тип файла
                        'message_type': message.message_type,
                        'timestamp': message.timestamp.isoformat(),
                        'is_read': message.is_read
                    }
                }
            )
        except json.JSONDecodeError:
            logger.error(f"Получены некорректные данные JSON")
            await self.send(text_data=json.dumps({
                'error': 'Некорректный формат данных'
            }))
        except Exception as e:
            logger.exception(f"Ошибка при обработке сообщения: {str(e)}")
            await self.send(text_data=json.dumps({
                'error': 'Ошибка при обработке сообщения'
            }))

    async def chat_message(self, event):
        """Отправка сообщения чата клиенту."""
        message = event['message']

        # Отправка сообщения через WebSocket
        await self.send(text_data=json.dumps({
            'message': message
        }))

        # Если сообщение от другого пользователя, отмечаем его как прочитанное
        # только если клиент, получающий сообщение, не является отправителем
        if message['sender_id'] != self.user.id:
            await self.mark_message_as_read(message['id'])

    @database_sync_to_async
    def user_has_chat_access(self, user, chat_id):
        """Проверка доступа пользователя к чату."""
        try:
            chat = Chat.objects.get(id=chat_id)
            # Проверяем, является ли пользователь администратором или партнером в этом чате
            if user.role == 'admin' and chat.admin == user:
                return True
            elif user.role == 'partner' and chat.partner == user:
                # Дополнительная проверка: партнеры могут общаться только с админами
                if chat.admin.role != 'admin':
                    logger.warning(
                        f"Партнер {user.id} пытается получить доступ к чату {chat_id}, который не с администратором")
                    return False
                return True

            logger.warning(f"Пользователь {user.id} пытается получить доступ к чату {chat_id} без прав")
            return False
        except Chat.DoesNotExist:
            logger.warning(f"Попытка доступа к несуществующему чату {chat_id}")
            return False

    @database_sync_to_async
    def save_message(self, message_type, content, file_data, file_name):
        """Сохранение сообщения в базе данных."""
        chat = Chat.objects.get(id=self.chat_id)

        # Создание сообщения
        message = Message(
            chat=chat,
            sender=self.user,
            content=content,
            message_type=message_type
        )

        # Обработка файла, если он присутствует
        if file_data and file_name:
            try:
                # Удаляем префикс data URL, если он присутствует
                if ';base64,' in file_data:
                    header, file_data = file_data.split(';base64,')

                # Декодируем данные base64
                file_content = base64.b64decode(file_data)

                # Проверяем размер файла
                if len(file_content) > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
                    raise ValueError(
                        f"Файл слишком большой. Максимальный размер: {settings.FILE_UPLOAD_MAX_MEMORY_SIZE / (1024 * 1024)} MB")

                # Создаем уникальное имя файла
                ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
                new_filename = f"{uuid.uuid4()}.{ext}" if ext else f"{uuid.uuid4()}"

                # Сохраняем файл
                message.file.save(new_filename, ContentFile(file_content), save=False)
            except Exception as e:
                logger.exception(f"Ошибка при сохранении файла: {str(e)}")
                raise

        # Сохраняем сообщение
        message.save()

        # Обновляем время последнего обновления чата
        chat.save()  # Это обновит updated_at через auto_now

        return message

    @database_sync_to_async
    def mark_message_as_read(self, message_id):
        """Отметка сообщения как прочитанного."""
        try:
            message = Message.objects.get(id=message_id)
            if not message.is_read:
                message.is_read = True
                message.save(update_fields=['is_read'])
        except Message.DoesNotExist:
            logger.warning(f"Попытка отметить несуществующее сообщение {message_id} как прочитанное")
            pass