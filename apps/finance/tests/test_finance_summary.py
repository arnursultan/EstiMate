import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from apps.orders.models import ProductRequest
from apps.products.models import Product
from django.urls import reverse
from rest_framework import status
from django.utils.timezone import now, timedelta
from apps.finance.models import PartnerFinanceStat, FinanceEntry
from apps.stores.models import Store, City, StoreDebt

User = get_user_model()

@pytest.fixture
def city():
    return City.objects.create(name="Алматы")

@pytest.fixture
def store(city):
    return Store.objects.create(
        name="Магазин 1",
        inn="123456789012",
        city=city,
        is_active=True,
        status="approved"
    )

@pytest.fixture
def product():
    return Product.objects.create(
        name="Товар",
        price=100.0,
        quantity=100,
        is_bonus_eligible=True
    )

@pytest.fixture
def partner_user(city):
    user = User.objects.create_user(
        email="partner@example.com",
        phone="+77001112233",
        first_name="Партнёр",
        last_name="Тестович",
        password="testpass123",
        role="partner",
    )
    user.city = city
    user.save()
    return user

@pytest.fixture
def admin_user(city):
    user = User.objects.create_superuser(
        email="admin@example.com",
        phone="+77000000000",
        first_name="Админ",
        last_name="Главный",
        password="adminpass123"
    )
    user.city = city
    user.save()
    return user

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



@pytest.mark.django_db
def test_admin_finance_summary_basic(admin_client, admin_user):
    today = now().date()

    PartnerFinanceStat.objects.create(
        user=admin_user,
        date=today,
        total_requested_amount=200,
        total_sold_amount=1000,
        total_expenses=300,
    )

    url = reverse("finance:finance-summary")
    response = admin_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    summary = response.json()["finance_summary"]
    assert summary["product_profit"] == 700.0



@pytest.mark.django_db
def test_partner_sees_only_own_stats(partner_client, partner_user, admin_user):
    today = now().date()

    PartnerFinanceStat.objects.create(
        user=partner_user,
        date=today,
        total_sold_amount=600,
        total_expenses=100,
    )

    PartnerFinanceStat.objects.create(
        user=admin_user,
        date=today,
        total_sold_amount=9999,
        total_expenses=0,
    )

    url = reverse("finance:finance-summary")
    response = partner_client.get(url)
    data = response.json()["finance_summary"]

    assert response.status_code == status.HTTP_200_OK
    assert data["product_profit"] == 500.0



@pytest.mark.django_db
def test_manual_entries_are_included(partner_client, partner_user, city):
    FinanceEntry.objects.create(
        user=partner_user,
        city=city,
        date=now().date(),
        entry_type='income',
        amount=300
    )
    FinanceEntry.objects.create(
        user=partner_user,
        city=city,
        date=now().date(),
        entry_type='expense',
        amount=100
    )

    url = reverse("finance:finance-summary")
    response = partner_client.get(url)
    data = response.json()["finance_summary"]

    assert response.status_code == status.HTTP_200_OK
    assert data["manual_income"] == 300.0
    assert data["manual_expense"] == 100.0
    assert data["manual_profit"] == 200.0



@pytest.mark.django_db
def test_date_filtering(partner_client, partner_user):
    today = now().date()
    ten_days_ago = today - timedelta(days=10)

    PartnerFinanceStat.objects.create(
        user=partner_user,
        date=ten_days_ago,
        total_sold_amount=5000,
        total_expenses=4000
    )

    PartnerFinanceStat.objects.create(
        user=partner_user,
        date=today,
        total_sold_amount=1000,
        total_expenses=200
    )

    url = reverse("finance:finance-summary")
    response = partner_client.get(url, {
        "from": (today - timedelta(days=1)).isoformat(),
        "to": today.isoformat()
    })
    data = response.json()["finance_summary"]

    assert response.status_code == status.HTTP_200_OK
    assert data["product_profit"] == 800.0  # только сегодняшняя запись


@pytest.mark.django_db
def test_partner_sees_only_their_store_debt(partner_client, partner_user, admin_user, store, product):
    StoreDebt.objects.create(store=store, amount=1000, is_paid=False)

    # Партнёр сделал запрос для магазина
    ProductRequest.objects.create(user=partner_user, store=store, product=product, quantity=1, request_type='STORE', damaged_quantity=0)

    # Другой магазин — не должен попасть
    other_store = Store.objects.create(name="Другой", inn="999999999999", city=store.city, status='approved', is_active=True)
    StoreDebt.objects.create(store=other_store, amount=5000, is_paid=False)

    url = reverse("finance:finance-summary")
    response = partner_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["finance_summary"]["outstanding_debt"] == 1000.0

@pytest.mark.django_db
def test_admin_filter_by_store(admin_client, admin_user, partner_user, store, product):
    test_date = now().date() - timedelta(days=2)

    # Партнёр делает запрос для магазина
    ProductRequest.objects.create(
        user=partner_user,
        store=store,
        product=product,
        quantity=1,
        request_type='STORE',
        damaged_quantity=0
    )

    PartnerFinanceStat.objects.create(
        user=partner_user,
        date=test_date,
        total_sold_amount=400,
        total_expenses=100,
    )

    url = reverse("finance:finance-summary")
    response = admin_client.get(url, {"store": store.id})

    assert response.status_code == status.HTTP_200_OK
    summary = response.json()["finance_summary"]
    assert summary["product_profit"] == 300.0



@pytest.mark.django_db
def test_admin_filter_by_city(admin_client, admin_user, partner_user, store, product):
    # Используем другую дату, чтобы не конфликтовать с предыдущим тестом
    other_day = now().date() - timedelta(days=1)

    ProductRequest.objects.create(
        user=partner_user,
        store=store,
        product=product,
        quantity=1,
        request_type='STORE',
        damaged_quantity=0
    )

    PartnerFinanceStat.objects.create(
        user=partner_user,
        date=other_day,
        total_sold_amount=200,
        total_expenses=50,
    )

    url = reverse("finance:finance-summary")
    response = admin_client.get(url, {"city": store.city.id})

    assert response.status_code == status.HTTP_200_OK
    summary = response.json()["finance_summary"]
    assert summary["product_profit"] == 150.0



@pytest.mark.django_db
def test_empty_summary_returns_zero(partner_client):
    url = reverse("finance:finance-summary")
    response = partner_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    summary = response.json()["finance_summary"]
    assert all(value == 0.0 for value in summary.values())


@pytest.mark.django_db
def test_summary_with_only_debt(partner_client, partner_user, store, product):
    # Запрос от партнёра, чтобы связать с магазином
    ProductRequest.objects.create(user=partner_user, product=product, store=store, quantity=1, request_type='STORE', damaged_quantity=0)
    StoreDebt.objects.create(store=store, amount=2000, is_paid=False)

    url = reverse("finance:finance-summary")
    response = partner_client.get(url)
    summary = response.json()["finance_summary"]

    assert summary["outstanding_debt"] == 2000.0
    assert summary["product_profit"] == 0.0  # стата отсутствует



@pytest.mark.django_db
def test_multiple_manual_entries_summed(partner_client, partner_user, city):
    today = now().date()
    FinanceEntry.objects.create(user=partner_user, city=city, date=today, entry_type='income', amount=100)
    FinanceEntry.objects.create(user=partner_user, city=city, date=today, entry_type='income', amount=300)
    FinanceEntry.objects.create(user=partner_user, city=city, date=today, entry_type='expense', amount=50)

    url = reverse("finance:finance-summary")
    response = partner_client.get(url)
    summary = response.json()["finance_summary"]

    assert summary["manual_income"] == 400.0
    assert summary["manual_expense"] == 50.0
    assert summary["manual_profit"] == 350.0


@pytest.mark.django_db
def test_summary_filters_out_old_data(partner_client, partner_user):
    old_day = now().date() - timedelta(days=30)
    today = now().date()

    PartnerFinanceStat.objects.create(user=partner_user, date=old_day, total_sold_amount=1000, total_expenses=100)

    url = reverse("finance:finance-summary")
    response = partner_client.get(url, {
        "from": (today - timedelta(days=1)).isoformat(),
        "to": today.isoformat(),
    })
    summary = response.json()["finance_summary"]
    assert summary["product_profit"] == 0.0  # старые записи не попали



@pytest.mark.django_db
def test_admin_filter_store_without_product_request(admin_client, store):
    StoreDebt.objects.create(store=store, amount=5000, is_paid=False)

    url = reverse("finance:finance-summary")
    response = admin_client.get(url, {"store": store.id})
    summary = response.json()["finance_summary"]
    assert summary["outstanding_debt"] == 5000.0 # Видит все без разбору

