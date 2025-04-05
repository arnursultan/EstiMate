from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from .models import Chat, Message
from django.contrib.auth import get_user_model
from project.asgi import application
import json
import base64

User = get_user_model()


class ChatAPITests(TestCase):
    """Тесты REST API для чата."""

    def setUp(self):
        """Создание тестовых данных и настройка клиентов."""
        # Создаем тестовых пользователей
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            phone='+996555123456',
            first_name='Admin',
            last_name='User',
            password='testpassword123',
            role='admin',
            status='approved',
            is_staff=True
        )

        self.partner_user = User.objects.create_user(
            email='partner@test.com',
            phone='+996555654321',
            first_name='Partner',
            last_name='User',
            password='testpassword123',
            role='partner',
            status='approved'
        )

        # Создаем тестовый чат
        self.chat = Chat.objects.create(
            admin=self.admin_user,
            partner=self.partner_user
        )

        # Создаем тестовые сообщения
        self.admin_message = Message.objects.create(
            chat=self.chat,
            sender=self.admin_user,
            content='Тестовое сообщение от администратора',
            message_type='text'
        )

        self.partner_message = Message.objects.create(
            chat=self.chat,
            sender=self.partner_user,
            content='Тестовое сообщение от партнера',
            message_type='text'
        )

        # Создаем API клиентов с токенами для аутентификации
        self.admin_client = APIClient()
        admin_token = RefreshToken.for_user(self.admin_user)
        self.admin_client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(admin_token.access_token)}')
        self.admin_token = str(admin_token.access_token)

        self.partner_client = APIClient()
        partner_token = RefreshToken.for_user(self.partner_user)
        self.partner_client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(partner_token.access_token)}')
        self.partner_token = str(partner_token.access_token)

    def test_chat_list_admin(self):
        """Тест получения списка чатов для администратора."""
        url = reverse('chat:chat-list')
        response = self.admin_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.chat.id)

        # Проверяем, что данные о последнем сообщении и непрочитанных сообщениях присутствуют
        self.assertIn('last_message', response.data[0])
        self.assertIn('unread_count', response.data[0])

    def test_chat_list_partner(self):
        """Тест получения списка чатов для партнера."""
        url = reverse('chat:chat-list')
        response = self.partner_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.chat.id)

    def test_message_list(self):
        """Тест получения списка сообщений."""
        url = reverse('chat:message-list', kwargs={'chat_id': self.chat.id})
        response = self.admin_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 2)

        # Проверяем пагинацию
        self.assertIn('count', response.data)
        self.assertIn('links', response.data)

    def test_create_text_message(self):
        """Тест создания текстового сообщения."""
        url = reverse('chat:message-create', kwargs={'chat_id': self.chat.id})
        data = {
            'content': 'Новое тестовое сообщение',
            'message_type': 'text'
        }

        response = self.admin_client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Проверка, что сообщение добавлено в базу данных
        self.assertEqual(Message.objects.count(), 3)
        message = Message.objects.latest('timestamp')
        self.assertEqual(message.content, 'Новое тестовое сообщение')
        self.assertEqual(message.sender, self.admin_user)

    def test_create_image_message(self):
        """Тест создания сообщения с изображением."""
        url = reverse('chat:message-create', kwargs={'chat_id': self.chat.id})

        # Создаем тестовый файл изображения
        image = SimpleUploadedFile(
            "test_image.jpg",
            b"file_content",
            content_type="image/jpeg"
        )

        data = {
            'content': 'Сообщение с изображением',
            'file': image,
            'message_type': 'image'
        }

        response = self.admin_client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Проверка наличия файла в сообщении
        message = Message.objects.latest('timestamp')
        self.assertEqual(message.message_type, 'image')
        self.assertIsNotNone(message.file)
        self.assertTrue('test_image' in message.file.name or '.jpg' in message.file.name)

    def test_mark_messages_as_read(self):
        """Тест отметки сообщений как прочитанных."""
        # Сначала убеждаемся, что сообщения не прочитаны
        self.admin_message.is_read = False
        self.admin_message.save()
        self.partner_message.is_read = False
        self.partner_message.save()

        url = reverse('chat:mark-messages-read', kwargs={'chat_id': self.chat.id})
        response = self.partner_client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('marked_count', response.data)

        # Проверяем, что сообщения от администратора отмечены как прочитанные
        self.admin_message.refresh_from_db()
        self.assertTrue(self.admin_message.is_read)

        # А сообщения партнера остались как есть (т.к. он сам их отправил)
        self.partner_message.refresh_from_db()
        self.assertFalse(self.partner_message.is_read)

    def test_access_restrictions(self):
        """Тест ограничений доступа к чатам."""
        # Создаем другого партнера
        other_partner = User.objects.create_user(
            email='other@test.com',
            phone='+996555111222',
            first_name='Other',
            last_name='Partner',
            password='testpassword123',
            role='partner',
            status='approved'
        )

        # Создаем другой чат
        other_chat = Chat.objects.create(
            admin=self.admin_user,
            partner=other_partner
        )

        # Создаем клиент для другого партнера
        other_client = APIClient()
        other_token = RefreshToken.for_user(other_partner)
        other_client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(other_token.access_token)}')

        # Пытаемся получить доступ к чату другого партнера
        url = reverse('chat:message-list', kwargs={'chat_id': self.chat.id})
        response = other_client.get(url)

        # Должно быть пусто (партнер не должен видеть чаты других партнеров)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)


class WebSocketTests(TestCase):
    """Тесты WebSocket соединений."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Создаем пользователей и токены
        cls.admin_user = User.objects.create_user(
            email='wsadmin@test.com',
            phone='+996555789456',
            first_name='WebSocket',
            last_name='Admin',
            password='testpassword123',
            role='admin',
            status='approved',
            is_staff=True
        )

        cls.partner_user = User.objects.create_user(
            email='wspartner@test.com',
            phone='+996555987654',
            first_name='WebSocket',
            last_name='Partner',
            password='testpassword123',
            role='partner',
            status='approved'
        )

        admin_token = RefreshToken.for_user(cls.admin_user)
        cls.admin_token = str(admin_token.access_token)

        partner_token = RefreshToken.for_user(cls.partner_user)
        cls.partner_token = str(partner_token.access_token)