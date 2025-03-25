import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.chats.models import Message

User = get_user_model()

MESSAGES_URL = reverse("message-list")


@pytest.fixture
def sender():
    return User.objects.create_user(
        email="sender@example.com",
        password="pass1234",
        role="partner",
        phone="+79991112233",
        first_name="Sender",
        last_name="User"
    )


@pytest.fixture
def receiver():
    return User.objects.create_user(
        email="receiver@example.com",
        password="pass1234",
        role="partner",
        phone="+79992223344",
        first_name="Receiver",
        last_name="User"
    )


@pytest.fixture
def api_client_sender(sender):
    client = APIClient()
    client.force_authenticate(user=sender)
    return client


@pytest.fixture
def api_client_receiver(receiver):
    client = APIClient()
    client.force_authenticate(user=receiver)
    return client


@pytest.mark.django_db
class TestMessageViewSet:

    def test_requires_auth(self, client):
        response = client.get(MESSAGES_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_returns_own_messages(self, api_client_sender, sender, receiver):
        Message.objects.create(sender=sender, receiver=receiver, type='text', text='1')
        Message.objects.create(sender=receiver, receiver=sender, type='text', text='2')
        Message.objects.create(sender=receiver, receiver=receiver, type='text', text='Should not see')

        response = api_client_sender.get(MESSAGES_URL)
        assert response.status_code == status.HTTP_200_OK
        texts = [msg['text'] for msg in response.data]
        assert '1' in texts
        assert '2' in texts
        assert 'Should not see' not in texts

    def test_create_message_success(self, api_client_sender, receiver):
        payload = {
            'receiver': receiver.id,
            'type': 'text',
            'text': 'Hello!'
        }
        response = api_client_sender.post(MESSAGES_URL, payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['text'] == 'Hello!'
        assert response.data['receiver'] == receiver.id

    def test_create_message_ignores_sender_field(self, api_client_sender, receiver):
        payload = {
            'sender': receiver.id,  # Попытка подменить
            'receiver': receiver.id,
            'type': 'text',
            'text': 'Fake sender'
        }
        response = api_client_sender.post(MESSAGES_URL, payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['sender'] != receiver.id  # sender должен быть текущий user

    def test_create_message_missing_fields(self, api_client_sender):
        response = api_client_sender.post(MESSAGES_URL, {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'type' in response.data

    def test_user_cannot_see_other_users_messages(self, api_client_receiver, sender):
        Message.objects.create(sender=sender, receiver=sender, type='text', text='Hidden')
        response = api_client_receiver.get(MESSAGES_URL)
        assert response.status_code == status.HTTP_200_OK
        assert all(msg['text'] != 'Hidden' for msg in response.data)
