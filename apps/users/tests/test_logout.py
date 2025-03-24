import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status

User = get_user_model()
LOGOUT_URL = reverse("logout")

@pytest.fixture
def user():
    return User.objects.create_user(
        email="logout@example.com",
        phone="+996700000000",
        first_name="Айбек",
        last_name="Логаутов",
        password="Test1234",
        is_active=True,
        status="approved"
    )

@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client

@pytest.fixture
def refresh_token(user):
    return str(RefreshToken.for_user(user))


# ❌ Неавторизован

@pytest.mark.django_db
def test_logout_unauthorized():
    client = APIClient()
    response = client.post(LOGOUT_URL)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "detail" in response.data
    assert "не были предоставлены" in response.data["detail"] or "credentials were not provided" in response.data["detail"]


# ❌ Нет refresh токена

@pytest.mark.django_db
def test_logout_missing_refresh(auth_client):
    response = auth_client.post(LOGOUT_URL, {})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["error"] == "Refresh-токен обязателен"


# ✅ Корректный refresh токен

@pytest.mark.django_db
def test_logout_with_valid_refresh(auth_client, refresh_token):
    response = auth_client.post(LOGOUT_URL, {"refresh": refresh_token})
    assert response.status_code == status.HTTP_200_OK
    assert response.data["message"] == "Вы успешно вышли"


# ❌ Некорректный refresh токен

@pytest.mark.django_db
def test_logout_with_invalid_refresh(auth_client):
    response = auth_client.post(LOGOUT_URL, {"refresh": "this.is.not.valid"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["error"] == "Неверный refresh-токен"
