import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.stores.models import City, Store


@pytest.fixture
def partner_user():
    return User.objects.create_user(
        email="partner@example.com",
        password="Partner123",
        first_name="Partner",
        last_name="User",
        phone="+996700000002",
        status="approved"
    )


@pytest.fixture
def partner_client(partner_user):
    client = APIClient()
    client.force_authenticate(user=partner_user)
    return client


@pytest.fixture
def city():
    return City.objects.create(name="Bishkek")


@pytest.fixture
def store(partner_user, city):
    return Store.objects.create(
        name="Test Store",
        inn="123456789012",
        address="Main St",
        phone="+996700000000",
        city=city,
        creator=partner_user,
        is_active=True,
        status="approved"
    )


@pytest.mark.django_db
def test_record_expense_success_without_store(partner_client):
    url = reverse("record-expense")
    data = {"amount": 150.75, "note": "Такси"}

    response = partner_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_200_OK
    assert "message" in response.data
    assert "entry_id" in response.data


@pytest.mark.django_db
def test_record_expense_success_with_store(partner_client, store):
    url = reverse("record-expense")
    data = {"amount": 200, "store_id": store.id, "note": "Доставка"}

    response = partner_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_200_OK
    assert "entry_id" in response.data
    assert response.data["message"].startswith("Расход на сумму")


@pytest.mark.django_db
def test_record_expense_missing_amount(partner_client):
    url = reverse("record-expense")
    data = {"note": "Без суммы"}

    response = partner_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Необходимо указать сумму" in response.data["error"]


@pytest.mark.django_db
def test_record_expense_negative_amount(partner_client):
    url = reverse("record-expense")
    data = {"amount": -50, "note": "Отрицательная сумма"}

    response = partner_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "должна быть положительным числом" in response.data["error"]


@pytest.mark.django_db
def test_record_expense_invalid_store(partner_client):
    url = reverse("record-expense")
    data = {"amount": 100, "store_id": 9999}

    response = partner_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "не найден" in response.data["error"]