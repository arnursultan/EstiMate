import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.stores.models import City, Store


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(
        email="admin@example.com",
        phone="77770000003",
        password="adminpass",
        first_name="Admin",
        last_name="Adminov"
    )

@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client

@pytest.fixture
def city():
    return City.objects.create(name="Тестовый город")

@pytest.fixture
def partner_user():
    return User.objects.create_user(
        email="partner@example.com",
        phone="77770000001",
        password="partnerpass",
        first_name="Партнёр",
        last_name="Тестович"
    )

@pytest.fixture
def store(city):
    return Store.objects.create(
        name="Магазин Тест",
        city=city,
        inn="123456789012",
        address="ул. Пушкина",
        phone="555555555",
        status="approved",
        is_active=True
    )


# ==== ТЕСТЫ ====

@pytest.mark.django_db
def test_admin_can_get_summary_statistics(admin_client):
    url = reverse("finance:admin-statistics")
    response = admin_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "summary" in data
    assert "date" in data

@pytest.mark.django_db
def test_filter_by_partner_id(admin_client, partner_user):
    from datetime import date
    from apps.finance.models import PartnerFinanceStat

    # Создаём заглушку для статистики
    PartnerFinanceStat.objects.create(
        user=partner_user,
        date=date.today()
    )

    url = reverse("finance:admin-statistics")
    response = admin_client.get(url, {"partner_id": partner_user.id})
    print(">>> RESPONSE JSON:", response.json())  # <-- Добавим это

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "partner" in data
    assert data["partner"]["id"] == partner_user.id

@pytest.mark.django_db
def test_filter_by_store_id(admin_client, store):
    url = reverse("finance:admin-statistics")
    response = admin_client.get(url, {"store_id": store.id})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "store" in data
    assert data["store"]["id"] == store.id

@pytest.mark.django_db
def test_filter_by_city_id(admin_client, city):
    url = reverse("finance:admin-statistics")
    response = admin_client.get(url, {"city_id": city.id})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "city" in data
    assert data["city"]["id"] == city.id

@pytest.mark.django_db
def test_invalid_date_returns_400(admin_client):
    url = reverse("finance:admin-statistics")
    response = admin_client.get(url, {"date": "not-a-date"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "error" in response.json()

@pytest.mark.django_db
def test_non_admin_gets_403(partner_user):
    client = APIClient()
    client.force_authenticate(user=partner_user)
    url = reverse("finance:admin-statistics")
    response = client.get(url)
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
def test_invalid_partner_id_returns_404(admin_client):
    url = reverse("finance:admin-statistics")
    response = admin_client.get(url, {"partner_id": 999999})
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "error" in response.json()


@pytest.mark.django_db
def test_invalid_store_id_returns_404(admin_client):
    url = reverse("finance:admin-statistics")
    response = admin_client.get(url, {"store_id": 999999})
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "error" in response.json()


@pytest.mark.django_db
def test_invalid_city_id_returns_404(admin_client):
    url = reverse("finance:admin-statistics")
    response = admin_client.get(url, {"city_id": 999999})
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "error" in response.json()


@pytest.mark.django_db
def test_filter_by_valid_date(admin_client):
    url = reverse("finance:admin-statistics")
    today = timezone.now().date().isoformat()
    response = admin_client.get(url, {"date": today})
    assert response.status_code == status.HTTP_200_OK
    assert "date" in response.json()
    assert response.json()["date"] == today



