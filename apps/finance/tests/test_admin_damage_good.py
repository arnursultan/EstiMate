from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.orders.models import ProductRequest
from apps.products.models import Product
from apps.users.models import User
from apps.stores.models import Store, City


@pytest.fixture
def admin_user():
    return User.objects.create_user(
        phone="9999999999",
        email="admin@test.com",
        first_name="Админ",
        last_name="Тестович",
        password="testpass123",
        is_staff=True
    )


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def partner_user():
    return User.objects.create_user(
        phone="7777777777",
        email="partner@test.com",
        first_name="Партнёр",
        last_name="Тестович",
        password="testpass123"
    )


@pytest.fixture
def city():
    return City.objects.create(name="Алматы")


@pytest.fixture
def store(city):
    return Store.objects.create(name="Магазин 1", inn="123456789012", city=city)


@pytest.mark.django_db
def test_damaged_report_basic(admin_client, partner_user, store, city):
    product = Product.objects.create(name="Товар", price=100)
    store.city = city
    store.save()

    ProductRequest.objects.create(
        user=partner_user,
        product=product,
        quantity=10,
        damaged_quantity=3,
        request_type="STORE",
        store=store,
        status="received"
    )

    date = timezone.now().date().isoformat()
    url = reverse("finance:damaged-goods-report")
    response = admin_client.get(url, {"date_from": date, "date_to": date})

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["summary"]["total_damaged_items"] == 3
    assert data["summary"]["total_loss"] == 300.0



@pytest.mark.django_db
def test_damaged_report_filtered_by_city(admin_client, partner_user, city, store):
    other_city = City.objects.create(name="Другой город")
    other_store = Store.objects.create(name="Other", inn="222222222222", city=other_city)

    product = Product.objects.create(name="Городской товар", price=80)

    ProductRequest.objects.create(
        user=partner_user,
        product=product,
        quantity=10,
        damaged_quantity=2,
        store=store,
        request_type="STORE",
        status="received"
    )

    ProductRequest.objects.create(
        user=partner_user,
        product=product,
        quantity=5,
        damaged_quantity=5,
        store=other_store,
        request_type="STORE",
        status="received"
    )

    url = reverse("finance:damaged-goods-report")
    response = admin_client.get(url, {"city": city.id})

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["summary"]["total_damaged_items"] == 2


@pytest.mark.django_db
def test_damaged_report_empty_returns_zero(admin_client):
    url = reverse("finance:damaged-goods-report")
    today = timezone.now().date().isoformat()

    response = admin_client.get(url, {"date_from": today, "date_to": today})
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["summary"]["total_damaged_items"] == 0
    assert data["summary"]["total_loss"] == 0.0

@pytest.mark.django_db
def test_damaged_report_basic(admin_client, admin_user, store, partner_user):
    product = Product.objects.create(name="Test Product", price=100)
    ProductRequest.objects.create(
        user=partner_user,
        store=store,
        product=product,
        quantity=10,
        damaged_quantity=3,
        status="received",
        request_type="STORE"
    )
    url = reverse("finance:damaged-goods-report")
    response = admin_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["summary"]["total_damaged_items"] == 3
    assert data["summary"]["total_loss"] == 300.0


@pytest.mark.django_db
def test_damaged_report_filter_by_store(admin_client, store, partner_user):
    product = Product.objects.create(name="Store Product", price=80)
    ProductRequest.objects.create(
        user=partner_user,
        store=store,
        product=product,
        quantity=5,
        damaged_quantity=2,
        status="received",
        request_type="STORE"
    )
    url = reverse("finance:damaged-goods-report")
    response = admin_client.get(url, {"store": store.id})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["summary"]["total_damaged_items"] == 2
    assert data["summary"]["total_loss"] == 160.0


@pytest.mark.django_db
def test_damaged_report_no_data_returns_zero(admin_client):
    old_date = (timezone.now() - timedelta(days=100)).date().isoformat()
    url = reverse("finance:damaged-goods-report")
    response = admin_client.get(url, {"date_from": old_date, "date_to": old_date})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["summary"]["total_damaged_items"] == 0
    assert data["summary"]["total_loss"] == 0.0


@pytest.mark.django_db
def test_damaged_report_ignores_zero_damaged(admin_client, store, partner_user):
    product = Product.objects.create(name="Zero Damaged", price=50)
    ProductRequest.objects.create(
        user=partner_user,
        store=store,
        product=product,
        quantity=5,
        damaged_quantity=0,
        status="received",
        request_type="STORE"
    )
    url = reverse("finance:damaged-goods-report")
    response = admin_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["summary"]["total_damaged_items"] == 0
    assert data["summary"]["total_loss"] == 0.0


@pytest.mark.django_db
def test_damaged_report_filter_by_city(admin_client, city, store, partner_user):
    store.city = city
    store.save()
    product = Product.objects.create(name="City Product", price=75)
    ProductRequest.objects.create(
        user=partner_user,
        store=store,
        product=product,
        quantity=6,
        damaged_quantity=2,
        status="received",
        request_type="STORE"
    )
    url = reverse("finance:damaged-goods-report")
    response = admin_client.get(url, {"city": city.id})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["summary"]["total_damaged_items"] == 2
    assert data["summary"]["total_loss"] == 150.0
