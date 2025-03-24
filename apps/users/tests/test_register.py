import pytest
from rest_framework.test import APIClient
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status

User = get_user_model()
REGISTER_URL = reverse("register")

@pytest.fixture
def client():
    return APIClient()

@pytest.fixture
def valid_user_data():
    def _data(**overrides):
        data = {
            "email": "user@gmail.com",
            "phone": "+996700123456",
            "first_name": "Айбек",
            "last_name": "Токтосунов",
            "password": "Pass1234"
        }
        data.update(overrides)
        return data
    return _data


# ✅ Успешная регистрация

@pytest.mark.django_db
def test_register_success(client, valid_user_data):
    data = valid_user_data()
    response = client.post(REGISTER_URL, data)
    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=data["email"])
    assert user.phone == data["phone"]
    assert user.role == "partner"
    assert user.status == "pending"
    assert user.check_password(data["password"])


# 🔻 Email

@pytest.mark.django_db
@pytest.mark.parametrize("email", [
    "toolong" + "a" * 45 + "@gmail.com",
    "bad..email@gmail.com",
    "user@bad-domain.com",
])
def test_register_invalid_emails(client, valid_user_data, email):
    data = valid_user_data(email=email, phone="+996700000001")
    response = client.post(REGISTER_URL, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.data


@pytest.mark.django_db
def test_register_duplicate_email(client, valid_user_data):
    User.objects.create_user(
        email="dupe@gmail.com",
        phone="+996700000002",
        first_name="Айбек",
        last_name="Тестов",
        password="Test1234"
    )
    data = valid_user_data(email="dupe@gmail.com", phone="+996700000003")
    response = client.post(REGISTER_URL, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.data


# 🔻 Phone

@pytest.mark.django_db
@pytest.mark.parametrize("phone", [
    "0700123456",
    "+99670012345",
    "+123456789012"
])
def test_register_invalid_phone_format(client, valid_user_data, phone):
    data = valid_user_data(phone=phone)
    response = client.post(REGISTER_URL, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "phone" in response.data


@pytest.mark.django_db
def test_register_duplicate_phone(client, valid_user_data):
    User.objects.create_user(
        email="phoneuser@gmail.com",
        phone="+996700000004",
        first_name="Тест",
        last_name="Телефон",
        password="Test1234"
    )
    data = valid_user_data(email="newuser@gmail.com", phone="+996700000004")
    response = client.post(REGISTER_URL, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "phone" in response.data


# 🔻 First name & Last name

@pytest.mark.django_db
@pytest.mark.parametrize("field,value", [
    ("first_name", "A"),
    ("first_name", "123"),
    ("last_name", "B"),
    ("last_name", "T0kto"),
])
def test_register_invalid_name_fields(client, valid_user_data, field, value):
    data = valid_user_data(**{field: value}, email="nameuser@gmail.com", phone="+996700000005")
    response = client.post(REGISTER_URL, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field in response.data


# 🔻 Password

@pytest.mark.django_db
@pytest.mark.parametrize("password", [
    "1234567",
    "password",
    "12345678",
])
def test_register_invalid_passwords(client, valid_user_data, password):
    data = valid_user_data(password=password, email="passuser@gmail.com", phone="+996700000006")
    response = client.post(REGISTER_URL, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "password" in response.data


# 🔻 Allowed domains

@pytest.mark.django_db
@pytest.mark.parametrize("domain", [
    "gmail.com", "mail.ru", "yahoo.com", "yandex.ru", "outlook.com"
])
def test_register_with_allowed_domains(client, valid_user_data, domain):
    email = f"user@{domain}"
    data = valid_user_data(email=email, phone="+996700000007")
    response = client.post(REGISTER_URL, data)
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
@pytest.mark.parametrize("domain", [
    "example.com", "protonmail.com", "hotmail.com", "test.org"
])
def test_register_with_disallowed_domains(client, valid_user_data, domain):
    email = f"user@{domain}"
    data = valid_user_data(email=email, phone="+996700000008")
    response = client.post(REGISTER_URL, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.data
