from datetime import timedelta
import pytest
from django.utils.timezone import now
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.products.models import Product
from apps.stores.models import Store, City
from django.urls import reverse
from rest_framework import status
from apps.orders.models import ProductRequest
from django.utils import timezone

User = get_user_model()

@pytest.fixture
def city():
    return City.objects.create(name="Алматы")

@pytest.fixture
def store(city):
    return Store.objects.create(name="Магазин 1", inn="123456789012", city=city, is_active=True, status="approved")

@pytest.fixture
def product():
    return Product.objects.create(name="Товар", price=100.0, quantity=50, is_bonus_eligible=True)

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
def test_partner_sees_only_their_requests(partner_client, partner_user, admin_user, product):
    ProductRequest.objects.create(user=partner_user, product=product, quantity=5, request_type='SELF')
    ProductRequest.objects.create(user=admin_user, product=product, quantity=10, request_type='SELF')

    url = reverse("finance:request-history")
    response = partner_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert all(item['user'] == partner_user.id for item in data)
    assert all("product_name" in item for item in data)

@pytest.mark.django_db
def test_admin_sees_all_requests(admin_client, partner_user, admin_user, product):
    ProductRequest.objects.create(user=partner_user, product=product, quantity=3, request_type='SELF')
    ProductRequest.objects.create(user=admin_user, product=product, quantity=7, request_type='SELF')

    url = reverse("finance:request-history")
    response = admin_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 2

@pytest.mark.django_db
def test_filter_by_status(admin_client, product, partner_user):
    ProductRequest.objects.create(user=partner_user, product=product, quantity=1, status='pending')
    ProductRequest.objects.create(user=partner_user, product=product, quantity=1, status='approved')

    url = reverse("finance:request-history")
    response = admin_client.get(url, {"status": "approved"})

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert all(req['status'] == 'approved' for req in data)

@pytest.mark.django_db
def test_search_by_product_name(admin_client, partner_user):
    p1 = Product.objects.create(name="Молоко", price=100)
    p2 = Product.objects.create(name="Хлеб", price=50)

    ProductRequest.objects.create(user=partner_user, product=p1, quantity=2)
    ProductRequest.objects.create(user=partner_user, product=p2, quantity=2)

    url = reverse("finance:request-history")
    response = admin_client.get(url, {"search": "Молоко"})

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert all("Молоко" in r["product_name"] for r in data)

@pytest.mark.django_db
def test_ordering_by_quantity(admin_client, partner_user, product):
    ProductRequest.objects.create(user=partner_user, product=product, quantity=1)
    ProductRequest.objects.create(user=partner_user, product=product, quantity=5)

    url = reverse("finance:request-history")
    response = admin_client.get(url, {"ordering": "-quantity"})

    assert response.status_code == status.HTTP_200_OK
    results = response.json()
    assert results[0]["quantity"] == 5

@pytest.mark.django_db
def test_filter_by_store(admin_client, partner_user, product, store):
    ProductRequest.objects.create(
        user=partner_user,
        product=product,
        store=store,
        request_type='STORE',
        partner_product=None,  # безопасно
        quantity=5,
        damaged_quantity=0
    )
    ProductRequest.objects.create(
        user=partner_user,
        product=product,
        request_type='SELF',
        quantity=5,
        damaged_quantity=0
    )

    url = reverse("finance:request-history")
    response = admin_client.get(url, {"store": store.id})
    data = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert all(req["store"] == store.id for req in data if req["store"] is not None)

@pytest.mark.django_db
def test_filter_by_date_range(admin_client, partner_user, product):
    old = timezone.now() - timedelta(days=10)
    new = timezone.now().replace(microsecond=0)

    req_old = ProductRequest.objects.create(user=partner_user, product=product, quantity=1, damaged_quantity=0)
    ProductRequest.objects.filter(id=req_old.id).update(created_at=old)

    req_new = ProductRequest.objects.create(user=partner_user, product=product, quantity=2, damaged_quantity=0)
    ProductRequest.objects.filter(id=req_new.id).update(created_at=new)

    url = reverse("finance:request-history")
    response = admin_client.get(url, {
        "created_at_after": (new - timedelta(minutes=1)).isoformat(),
        "created_at_before": (new + timedelta(minutes=1)).isoformat(),
    })

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == req_new.id





