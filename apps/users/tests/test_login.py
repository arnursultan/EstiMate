import pytest
from rest_framework.test import APIClient
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status

User = get_user_model()
LOGIN_URL = reverse("login")

@pytest.fixture
def client():
    return APIClient()

@pytest.fixture
def active_user():
    return User.objects.create_user(
        email="user@gmail.com",
        phone="+996700123456",
        first_name="Айбек",
        last_name="Тестов",
        password="Test1234",
        status="approved",
        is_active=True
    )

@pytest.mark.django_db
def test_login_success(client, active_user):
    data = {
        "email": active_user.email,
        "password": "Test1234"
    }
    response = client.post(LOGIN_URL, data)
    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    assert "refresh" in response.data


@pytest.mark.django_db
def test_login_wrong_email(client):
    data = {
        "email": "wrong@gmail.com",
        "password": "Test1234"
    }
    response = client.post(LOGIN_URL, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Неверный email" in str(response.data)


@pytest.mark.django_db
def test_login_wrong_password(client, active_user):
    data = {
        "email": active_user.email,
        "password": "WrongPass123"
    }
    response = client.post(LOGIN_URL, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Неверный пароль" in str(response.data)


@pytest.mark.django_db
def test_login_inactive_user(client):
    user = User.objects.create_user(
        email="inactive@gmail.com",
        phone="+996700000000",
        first_name="Ин",
        last_name="Актив",
        password="Test1234",
        is_active=False,
        status="approved"
    )
    data = {
        "email": "inactive@gmail.com",
        "password": "Test1234"
    }
    response = client.post(LOGIN_URL, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Ваш аккаунт заблокирован" in str(response.data)


@pytest.mark.django_db
@pytest.mark.parametrize("status_value, expected_message", [
    ("pending", "еще не одобрен"),
    ("rejected", "была отклонена"),
])
def test_login_blocked_statuses(client, status_value, expected_message):
    user = User.objects.create_user(
        email=f"{status_value}@gmail.com",
        phone="+996700000001",
        first_name="Пользователь",
        last_name=status_value,
        password="Test1234",
        is_active=True,
        status=status_value
    )
    data = {
        "email": user.email,
        "password": "Test1234"
    }
    response = client.post(LOGIN_URL, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert expected_message in str(response.data)
