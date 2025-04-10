from datetime import timedelta

import pytest
from decimal import Decimal
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from apps.finance.models import FinanceEntry
from apps.products.models import PartnerProduct, Product
from apps.stores.models import Store, City
from apps.users.models import User


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
def finance_entries(partner_user, admin_user, partner_product):
    today = timezone.now().date()
    e1 = FinanceEntry.objects.create(
        user=partner_user,
        entry_type="income",
        amount=200,
        date=today,
        note="доход партнёра"
    )
    e2 = FinanceEntry.objects.create(
        user=partner_user,
        entry_type="expense",
        amount=100,
        date=today,
        note="расход партнёра"
    )
    e3 = FinanceEntry.objects.create(
        user=admin_user,
        entry_type="income",
        amount=500,
        date=today,
        note="доход админа",
        partner_product=partner_product
    )
    return [e1, e2, e3]

@pytest.fixture
def product():
    return Product.objects.create(
        name="Продукт",
        price=100,
        quantity=100,
        is_bonus_eligible=True
    )

@pytest.fixture
def partner_product(product, partner_user):
    return PartnerProduct.objects.create(
        partner=partner_user,
        product=product,
        quantity=20,
        sold_quantity=0,
        damaged_quantity=0,
        bonus_quantity=0,
        returned_quantity=0,
        price=100
    )

@pytest.mark.django_db
def test_partner_sees_only_own_entries(partner_client, finance_entries):
    url = reverse("finance:finance-entry-list")
    response = partner_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 2
    assert all(entry["note"] != "доход админа" for entry in data)


@pytest.mark.django_db
def test_admin_sees_all_entries(admin_client, finance_entries):
    url = reverse("finance:finance-entry-list")
    response = admin_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 3
    notes = [entry["note"] for entry in data]
    assert "доход админа" in notes


@pytest.mark.django_db
def test_ordering_by_amount_desc(partner_client, partner_user):
    today = timezone.now().date()
    FinanceEntry.objects.create(user=partner_user, entry_type="income", amount=100, date=today, note="меньше")
    FinanceEntry.objects.create(user=partner_user, entry_type="income", amount=200, date=today, note="больше")

    url = reverse("finance:finance-entry-list")
    response = partner_client.get(url, {"ordering": "-amount"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    amounts = [Decimal(entry["amount"]) for entry in data]
    assert amounts == sorted(amounts, reverse=True)


@pytest.mark.django_db
def test_filter_by_entry_type(partner_client, finance_entries):
    url = reverse("finance:finance-entry-list")
    response = partner_client.get(url, {"entry_type": "income"})
    assert response.status_code == status.HTTP_200_OK
    assert all(entry["entry_type"] == "income" for entry in response.json())


@pytest.mark.django_db
def test_filter_by_date(partner_client, finance_entries):
    today = timezone.now().date().isoformat()
    url = reverse("finance:finance-entry-list")
    response = partner_client.get(url, {"date": today})
    assert response.status_code == status.HTTP_200_OK
    assert all(entry["date"] == today for entry in response.json())


@pytest.mark.django_db
def test_invalid_filter_returns_400(partner_client, finance_entries):
    url = reverse("finance:finance-entry-list")
    response = partner_client.get(url, {"entry_type": "abracadabra"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_unauthenticated_cannot_access():
    client = APIClient()
    url = reverse("finance:finance-entry-list")
    response = client.get(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_ordering_by_date_asc(partner_client, partner_user):
    yesterday = timezone.now().date() - timedelta(days=1)
    today = timezone.now().date()

    FinanceEntry.objects.create(user=partner_user, entry_type="income", amount=100, date=today, note="сегодня")
    FinanceEntry.objects.create(user=partner_user, entry_type="income", amount=200, date=yesterday, note="вчера")

    url = reverse("finance:finance-entry-list")
    response = partner_client.get(url, {"ordering": "date"})
    dates = [entry["date"] for entry in response.json()]
    assert dates == sorted(dates)


