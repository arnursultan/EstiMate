import pytest
from django.urls import reverse
from rest_framework import status
from django.core.cache import cache
from apps.users.models import User
from unittest.mock import patch
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.test import APIClient
RESET_URL = reverse("password_reset")
VERIFY_URL = reverse("password_reset_verify")
CONFIRM_URL = reverse("password_reset_confirm")
REFRESH_URL = reverse("token_refresh")
@pytest.fixture
def user():
    return User.objects.create_user(
        email="reset@example.com",
        phone="+996700000001",
        password="Pass1234",
        first_name="Айбек",
        last_name="Профиль"
    )

@pytest.fixture
def client():
    return APIClient()

@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_token_refresh_success(auth_client, user):
    refresh = RefreshToken.for_user(user)
    response = auth_client.post(REFRESH_URL, {"refresh": str(refresh)})
    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data

@pytest.mark.django_db
def test_token_refresh_invalid_token(auth_client):
    invalid_token = "invalid.token.value"
    response = auth_client.post(REFRESH_URL, {"refresh": invalid_token})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "error" in response.data
    assert response.data["error"] == "Refresh-токен недействителен, войдите заново."



@pytest.mark.django_db
@patch("apps.users.views.send_reset_email.delay")
def test_password_reset_success(mock_send_email, client, user):
    response = client.post(RESET_URL, {"email": user.email})
    assert response.status_code == status.HTTP_200_OK
    assert "message" in response.data
    user.refresh_from_db()
    assert user.token_reset is not None
    assert cache.get(f"reset_token_valid:{user.token_reset}") is True
    mock_send_email.assert_called_once()

@pytest.mark.django_db
def test_password_reset_user_not_found(client):
    response = client.post(RESET_URL, {"email": "notfound@example.com"})
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.data["error"] == "Пользователь не найден"

@pytest.mark.django_db
def test_password_verify_success(client, user):
    user.token_reset = "12345"
    user.save()
    cache.set("reset_token_valid:12345", True, timeout=120)

    response = client.post(VERIFY_URL, {"token": "12345"})
    assert response.status_code == status.HTTP_200_OK
    assert response.data["message"] == "Код подтверждён"

@pytest.mark.django_db
def test_password_verify_invalid_token(client):
    response = client.post(VERIFY_URL, {"token": "00000"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["error"] == "Срок действия токена истёк."

@pytest.mark.django_db
def test_password_confirm_success(client, user):
    user.token_reset = "67890"
    user.save()
    cache.set("reset_token_valid:67890", True, timeout=120)

    data = {
        "token": "67890",
        "new_password": "NewPass123",
        "confirm_password": "NewPass123"
    }
    response = client.post(CONFIRM_URL, data)
    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.check_password("NewPass123")
    assert user.token_reset is None

@pytest.mark.django_db
def test_password_confirm_mismatch(client, user):
    data = {
        "token": "abcde",
        "new_password": "NewPass123",
        "confirm_password": "WrongPass"
    }
    response = client.post(CONFIRM_URL, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["error"] == "Пароли не совпадают."