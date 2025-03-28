import pytest
from datetime import date
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.stores.models import Store, City, StoreDebt
from apps.finance.models import StoreFinanceStat
from apps.orders.models import ProductRequest
from apps.products.models import Product

User = get_user_model()


# ----------------------------
# 🔧 Фикстуры
# ----------------------------

@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin@example.com",
        phone="+996700000000",
        first_name="Admin",
        last_name="User",
        password="pass",
        is_staff=True
    )

@pytest.fixture
def auth_admin(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client

@pytest.fixture
def city():
    return City.objects.create(name="Ош")

@pytest.fixture
def store(city):
    return Store.objects.create(name="Магазин Тест", city=city)

@pytest.fixture
def product():
    return Product.objects.create(name="Тест продукт", quantity=1000, price=100)

@pytest.fixture
def setup_finance_data(store, product, admin_user):
    today = timezone.now().date()

    StoreFinanceStat.objects.create(
        store=store,
        date=today,
        total_approved=500000,
        total_damaged=10000,
        total_debt=200000,
    )

    ProductRequest.objects.create(
        product=product,
        user=admin_user,
        quantity=420,
        bonus_quantity=20,
        damaged_quantity=10,
        store=store,
        status="received"
    )

    StoreDebt.objects.create(
        store=store,
        amount=45000,
        is_paid=True,
        paid_at=timezone.now(),
        created_by=admin_user
    )


# ----------------------------
# ✅ Тесты
# ----------------------------

@pytest.mark.django_db
def test_admin_finance_stat_all(auth_admin, setup_finance_data):
    url = reverse('finance:admin-finance-stat')
    response = auth_admin.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["metrics"]
    assert data["income"] == 500000
    assert data["damaged_loss"] == 10000
    assert data["debt"] == 200000
    assert data["bonus"] == 20
    assert data["repaid_debt"] == 45000
    assert "remaining_stock" in data
    assert "profit" in data
    assert "balance" in data


@pytest.mark.django_db
def test_admin_finance_stat_city(auth_admin, setup_finance_data, store):
    url = reverse('finance:admin-finance-stat')
    response = auth_admin.get(url, {"city": store.city.id})
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["filters"]["city"] == str(store.city.id)


@pytest.mark.django_db
def test_admin_finance_stat_store(auth_admin, setup_finance_data, store):
    url = reverse('finance:admin-finance-stat')
    response = auth_admin.get(url, {"store": store.id})
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["filters"]["store"] == str(store.id)


@pytest.mark.django_db
def test_admin_finance_stat_date_filter(auth_admin, setup_finance_data):
    today = timezone.now().date()
    url = reverse('finance:admin-finance-stat')
    response = auth_admin.get(url, {
        "date_from": today.isoformat(),
        "date_to": today.isoformat()
    })
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["date_range"]["from"] == today.isoformat()


@pytest.mark.django_db
def test_admin_finance_stat_permission():
    client = APIClient()  # неавторизованный
    url = reverse('finance:admin-finance-stat')
    response = client.get(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.fixture
def regular_user(db):
    return User.objects.create_user(
        email="user@example.com",
        phone="+996700000999",
        first_name="Обычный",
        last_name="Юзер",
        password="userpass",
        is_staff=False  # главное!
    )

@pytest.fixture
def auth_regular(regular_user):
    client = APIClient()
    client.force_authenticate(user=regular_user)
    return client


@pytest.mark.django_db
def test_non_admin_user_cannot_access_admin_finance_stat(auth_regular):
    url = reverse('finance:admin-finance-stat')
    response = auth_regular.get(url)
    assert response.status_code == status.HTTP_403_FORBIDDEN