import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.notifications.models import Notification


@pytest.fixture
def user():
    return User.objects.create_user(
        email="user@example.com",
        password="Test1234",
        phone="+996700000001",
        first_name="John",
        last_name="Doe"
    )


@pytest.fixture
def another_user():
    return User.objects.create_user(
        email="another@example.com",
        password="Test1234",
        phone="+996700000002",
        first_name="Jane",
        last_name="Smith"
    )


@pytest.fixture
def user_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def notifications(user, another_user):
    return [
        Notification.objects.create(recipient=user, title="Title 1", message="Message 1"),
        Notification.objects.create(recipient=user, title="Title 2", message="Message 2", is_read=True),
        Notification.objects.create(recipient=another_user, title="Other", message="Other")
    ]


@pytest.mark.django_db
def test_list_notifications(user_client, notifications):
    url = reverse("notification-list")
    response = user_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 2
    assert all(n["title"] != "Other" for n in response.data)


@pytest.mark.django_db
def test_mark_all_read(user_client, notifications):
    url = reverse("notification-mark-all-read")
    response = user_client.post(url)

    assert response.status_code == status.HTTP_200_OK
    assert Notification.objects.filter(recipient=notifications[0].recipient, is_read=False).count() == 0


@pytest.mark.django_db
def test_mark_single_notification_read(user_client, notifications):
    notification = notifications[0]
    assert notification.is_read is False

    url = reverse("notification-mark-read", args=[notification.id])
    response = user_client.post(url)

    notification.refresh_from_db()
    assert response.status_code == status.HTTP_200_OK
    assert notification.is_read is True


@pytest.mark.django_db
def test_cannot_mark_others_notification(user_client, notifications):
    other_notification = notifications[2]
    url = reverse("notification-mark-read", args=[other_notification.id])
    response = user_client.post(url)

    assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]


@pytest.mark.django_db
def test_mark_already_read_notification(user_client, notifications):
    already_read = notifications[1]
    url = reverse("notification-mark-read", args=[already_read.id])
    response = user_client.post(url)

    already_read.refresh_from_db()
    assert response.status_code == status.HTTP_200_OK
    assert already_read.is_read is True


@pytest.mark.django_db
def test_mark_invalid_notification(user_client):
    url = reverse("notification-mark-read", args=[9999])
    response = user_client.post(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND
