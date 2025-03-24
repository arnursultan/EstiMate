import pytest
from rest_framework.test import APIClient
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
import io
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile


User = get_user_model()
PROFILE_URL = reverse("profile")

@pytest.fixture
def user():
    return User.objects.create_user(
        email="me@gmail.com",
        phone="+996700123456",
        first_name="Айбек",
        last_name="Профиль",
        password="Test1234",
        is_active=True,
        status="approved"
    )

@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client

# 🔓 Неавторизован
@pytest.mark.django_db
def test_get_profile_unauthorized():
    client = APIClient()
    response = client.get(PROFILE_URL)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "detail" in response.data

# 🔐 Авторизован
@pytest.mark.django_db
def test_get_profile_success(auth_client, user):
    response = auth_client.get(PROFILE_URL)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["email"] == user.email
    assert response.data["phone"] == user.phone
    assert response.data["first_name"] == user.first_name
    assert response.data["last_name"] == user.last_name
    assert "password" not in response.data



# ✅ Успешное обновление одного поля (PATCH)

@pytest.mark.django_db
def test_patch_profile_first_name(auth_client, user):
    response = auth_client.patch(PROFILE_URL, {"first_name": "Нурбек"})
    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.first_name == "Нурбек"


# ❌ Дубликат email

@pytest.mark.django_db
def test_patch_profile_duplicate_email(auth_client, user):
    User.objects.create_user(
        email="dupe@gmail.com",
        phone="+996700000099",
        first_name="Test",
        last_name="User",
        password="Test1234"
    )
    response = auth_client.patch(PROFILE_URL, {"email": "dupe@gmail.com"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.data


# ❌ Некорректное имя

@pytest.mark.django_db
def test_patch_profile_invalid_first_name(auth_client):
    response = auth_client.patch(PROFILE_URL, {"first_name": "123"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "first_name" in response.data


# ✅ Обновление пароля

@pytest.mark.django_db
def test_patch_profile_password(auth_client, user):
    response = auth_client.patch(PROFILE_URL, {"password": "NewPass123"})
    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.check_password("NewPass123")


# 📸 Успешное обновление фото
@pytest.mark.django_db
def test_patch_profile_photo(auth_client, user):
    image = Image.new("RGB", (100, 100))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)

    photo_file = SimpleUploadedFile(
        name="avatar.jpg",
        content=buffer.read(),
        content_type="image/jpeg"
    )

    response = auth_client.patch(PROFILE_URL, {"photo": photo_file}, format="multipart")

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert bool(user.photo) is True


# ❌ Некорректное фото больше 5 мб
@pytest.mark.django_db
def test_patch_profile_photo_too_large(auth_client):
    big_file = SimpleUploadedFile(
        "big_image.jpg",
        content=b"a" * 6 * 1024 * 1024,
        content_type="image/jpeg"
    )

    response = auth_client.patch(PROFILE_URL, {"photo": big_file}, format="multipart")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "photo" in response.data
    assert "Файл" in response.data["photo"][0] or "изображение" in response.data["photo"][0]


#Файл не является изображением
@pytest.mark.django_db
def test_patch_profile_photo_invalid_type(auth_client):
    fake_image = SimpleUploadedFile(
        "not_an_image.txt",
        content="Это не изображение".encode("utf-8"),
        content_type="text/plain"
    )

    response = auth_client.patch(PROFILE_URL, {"photo": fake_image}, format="multipart")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "photo" in response.data
    assert "Файл" in response.data["photo"][0] or "изображение" in response.data["photo"][0]


@pytest.mark.django_db
def test_put_profile_success(auth_client, user):
    new_data = {
        "email": "updated@gmail.com",
        "phone": "+996700000099",
        "first_name": "Айдар",
        "last_name": "Тестов",
        "password": "NewPass123"
    }
    response = auth_client.put(PROFILE_URL, new_data)
    assert response.status_code == status.HTTP_200_OK

    user.refresh_from_db()
    assert user.email == new_data["email"]
    assert user.phone == new_data["phone"]
    assert user.first_name == "Айдар"
    assert user.last_name == "Тестов"
    assert user.check_password("NewPass123")


# ❌ Пропущено обязательное поле (например, email)
@pytest.mark.django_db
def test_put_profile_missing_required(auth_client):
    data = {
        "phone": "+996700000011",
        "first_name": "Тест",
        "last_name": "Тестов",
        "password": "Pass1234"
    }
    response = auth_client.put(PROFILE_URL, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.data


# ✅ Деактивация аккаунта
@pytest.mark.django_db
def test_deactivate_account_success(auth_client, user):
    url = reverse("deactivate")  # Убедись, что в urls.py name="deactivate"
    response = auth_client.post(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["detail"] == "Ваш аккаунт успешно деактивирован."

    user.refresh_from_db()
    assert user.is_active is False



