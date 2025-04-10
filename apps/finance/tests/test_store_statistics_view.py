import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.utils import timezone
from datetime import timedelta
from apps.users.models import User
from apps.stores.models import Store, City
from apps.orders.models import ProductRequest
from apps.products.models import Product
from apps.finance.models import StoreFinanceStat

# === FIXTURES ===

@pytest.fixture
def city():
    return City.objects.create(name="Тестовый город")

@pytest.fixture
def store(city):
    return Store.objects.create(
        name="StoreTest",
        inn="123456789012",
        city=city,
        address="Test Address",
        phone="+996700000055",
        status="approved",
        is_active=True,

    )

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
def partner_user():
    return User.objects.create_user(
        email="partner@example.com",
        phone="77770000001",
        password="partnerpass",
        first_name="Партнёр",
        last_name="Тестович"
    )

@pytest.fixture
def partner_client(partner_user):
    client = APIClient()
    client.force_authenticate(user=partner_user)
    return client

@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client

@pytest.fixture
def product():
    return Product.objects.create(name="Продукт", price=100)

@pytest.fixture
def product_request(partner_user, store, product):
    return ProductRequest.objects.create(
        user=partner_user,
        store=store,
        product=product,
        quantity=5,
        request_type="STORE",  # Используем правильное поле
    )

@pytest.fixture
def store_stat(store):
    date = timezone.now().date()
    store_stat, created = StoreFinanceStat.objects.get_or_create(
        store=store,
        date=date,
        defaults={
            'total_received_quantity': 5,
            'total_bonus_quantity': 1,
            'total_damaged_quantity': 0,
            'total_debt': 500,
            'total_paid_debt': 300,
            'total_partner_expenses': 50,
            'profit': 150
        }
    )
    return store_stat

# === TESTS ===

@pytest.mark.django_db
def test_admin_can_get_statistics(admin_client, store_stat):
    url = reverse("finance:store-statistics")
    response = admin_client.get(f"{url}?store_id={store_stat.store.id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["store"]["id"] == store_stat.store.id
    assert data["damaged"]["quantity"] == store_stat.total_damaged_quantity
    assert "profit" in data

@pytest.mark.django_db
def test_partner_with_access_can_get_statistics(partner_client, store, product_request, store_stat):
    url = reverse("finance:store-statistics")
    response = partner_client.get(f"{url}?store_id={store.id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["store"]["name"] == store.name
    assert data["bonus"]["quantity"] == store_stat.total_bonus_quantity

@pytest.mark.django_db
def test_partner_without_access_gets_403(partner_client, store):
    url = reverse("finance:store-statistics")
    response = partner_client.get(f"{url}?store_id={store.id}")
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "error" in response.json()

@pytest.mark.django_db
def test_missing_store_id_returns_400(admin_client):
    url = reverse("finance:store-statistics")
    response = admin_client.get(url)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "Необходимо указать ID магазина"

@pytest.mark.django_db
def test_invalid_store_id_returns_404(admin_client):
    url = reverse("finance:store-statistics")
    response = admin_client.get(f"{url}?store_id=9999")
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.django_db
def test_invalid_date_format_returns_400(admin_client, store):
    url = reverse("finance:store-statistics")
    response = admin_client.get(f"{url}?store_id={store.id}&date=bad-date")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "формат" in response.json()["error"]


@pytest.mark.django_db
def test_old_date_returns_statistics(admin_client, store):
    old_date = (timezone.now() - timedelta(days=365 * 10)).date()  # 10 лет назад
    url = reverse("finance:store-statistics")
    response = admin_client.get(f"{url}?store_id={store.id}&date={old_date}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["store"]["id"] == store.id

@pytest.mark.django_db
def test_future_date_returns_statistics(admin_client, store):
    future_date = (timezone.now() + timedelta(days=1)).date()  # Завтрашняя дата
    url = reverse("finance:store-statistics")
    response = admin_client.get(f"{url}?store_id={store.id}&date={future_date}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["store"]["id"] == store.id

@pytest.mark.django_db
def test_zero_values_in_response(admin_client, store, store_stat):
    store_stat.total_received_quantity = 0
    store_stat.total_bonus_quantity = 0
    store_stat.total_damaged_quantity = 0
    store_stat.total_debt = 0
    store_stat.total_paid_debt = 0
    store_stat.total_partner_expenses = 0
    store_stat.profit = 0
    store_stat.save()

    url = reverse("finance:store-statistics")
    response = admin_client.get(f"{url}?store_id={store.id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["requested"]["quantity"] == 0
    assert data["bonus"]["quantity"] == 0
    assert data["damaged"]["quantity"] == 0
    assert data["debt"]["current"] == 0
    assert data["debt"]["paid"] == 0
    assert data["expenses"] == 0
    assert data["profit"] == 0