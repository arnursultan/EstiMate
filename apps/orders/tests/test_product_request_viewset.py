import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.products.models import Product, Category
from apps.orders.models import ProductRequest
from apps.stores.models import Store
from django.utils.timezone import now


@pytest.fixture
def admin():
    return User.objects.create_user(
        email="admin@example.com",
        password="Admin123",
        first_name="Admin",
        last_name="User",
        phone="+996700000001",
        is_staff=True
    )


@pytest.fixture
def partner():
    return User.objects.create_user(
        email="partner@example.com",
        password="Partner123",
        first_name="Partner",
        last_name="User",
        phone="+996700000002",
        status="approved"
    )


@pytest.fixture
def admin_client(admin):
    client = APIClient()
    client.force_authenticate(user=admin)
    return client


@pytest.fixture
def partner_client(partner):
    client = APIClient()
    client.force_authenticate(user=partner)
    return client


@pytest.fixture
def category():
    return Category.objects.create(name="Water")


@pytest.fixture
def product(category):
    return Product.objects.create(
        name="Bonaqua",
        category=category,
        price=50,
        quantity=100
    )


@pytest.fixture
def store(partner, city):
    return Store.objects.create(
        name="My Store",
        inn="123456789012",
        address="Main Street",
        phone="+996777777777",
        city=city,
        owner=partner,
        is_active=True
    )


@pytest.fixture
def city():
    from apps.stores.models import City
    return City.objects.create(name="Bishkek")

@pytest.mark.django_db
def test_create_product_request_success(partner_client, product):
    url = reverse("product-requests-list")
    data = {"product": product.id, "quantity": 5, "for_store": False}
    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_201_CREATED
    assert ProductRequest.objects.count() == 1


@pytest.mark.django_db
def test_create_request_insufficient_stock(partner_client, product):
    url = reverse("product-requests-list")
    data = {"product": product.id, "quantity": 999, "for_store": False}
    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_create_request_for_store_without_store(partner_client, product):
    url = reverse("product-requests-list")
    data = {"product": product.id, "quantity": 2, "for_store": True}
    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_list_product_requests_admin_vs_partner(admin_client, partner_client, product, partner):
    # Создание заявок от партнёра
    ProductRequest.objects.create(product=product, quantity=1, user=partner)
    ProductRequest.objects.create(product=product, quantity=2, user=partner)

    admin_response = admin_client.get(reverse("product-requests-list"))
    partner_response = partner_client.get(reverse("product-requests-list"))

    assert len(admin_response.data) >= 2
    assert len(partner_response.data) == 2


@pytest.mark.django_db
def test_update_status_by_admin(admin_client, partner, product):
    req = ProductRequest.objects.create(product=product, quantity=3, user=partner, status='pending')
    url = reverse("product-requests-update-status", args=[req.id])
    response = admin_client.post(url, {"status": "approved"})
    assert response.status_code == status.HTTP_200_OK
    req.refresh_from_db()
    assert req.status == "approved"


@pytest.mark.django_db
def test_mark_received_success(partner_client, partner, product):
    req = ProductRequest.objects.create(product=product, quantity=3, user=partner, status='approved')
    url = reverse("product-requests-mark-received", args=[req.id])
    response = partner_client.post(url, {})
    assert response.status_code == status.HTTP_200_OK
    req.refresh_from_db()
    assert req.status == "received"


@pytest.mark.django_db
def test_report_damaged_success(partner_client, partner, product):
    req = ProductRequest.objects.create(product=product, quantity=5, user=partner, status='received')
    url = reverse("product-requests-report-damaged", args=[req.id])
    response = partner_client.post(url, {"damaged_quantity": 2})
    assert response.status_code == status.HTTP_200_OK
    req.refresh_from_db()
    assert req.damaged_quantity == 2


@pytest.mark.django_db
def test_bulk_create_success(partner_client, product):
    url = reverse("product-requests-bulk-create")
    data = [{"product": product.id, "quantity": 2, "for_store": False},
            {"product": product.id, "quantity": 3, "for_store": False}]
    response = partner_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert ProductRequest.objects.count() == 2


@pytest.mark.django_db
def test_cart_view(partner_client, partner, product):
    ProductRequest.objects.create(product=product, quantity=2, user=partner, status='approved', for_store=False)
    ProductRequest.objects.create(product=product, quantity=1, user=partner, status='pending', for_store=False)

    url = reverse("product-requests-cart")
    response = partner_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert all(r['status'] == 'approved' for r in response.data)


@pytest.mark.django_db
def test_daily_report(partner_client, partner, product):
    ProductRequest.objects.create(product=product, quantity=3, user=partner, status='received', created_at=now())
    url = reverse("product-requests-daily-report")
    response = partner_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["total_quantity"] == 3


@pytest.mark.django_db
def test_partner_cannot_update_status(partner_client, partner, product):
    req = ProductRequest.objects.create(product=product, quantity=3, user=partner, status='pending')
    url = reverse("product-requests-update-status", args=[req.id])
    response = partner_client.post(url, {"status": "approved"})
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_admin_cannot_mark_received(admin_client, partner, product):
    req = ProductRequest.objects.create(product=product, quantity=2, user=partner, status='approved')
    url = reverse("product-requests-mark-received", args=[req.id])
    response = admin_client.post(url, {})
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_report_damaged_invalid_status(partner_client, partner, product):
    req = ProductRequest.objects.create(product=product, quantity=2, user=partner, status='approved')
    url = reverse("product-requests-report-damaged", args=[req.id])
    response = partner_client.post(url, {"damaged_quantity": 1})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_report_damaged_more_than_received(partner_client, partner, product):
    req = ProductRequest.objects.create(product=product, quantity=3, user=partner, status='received')
    url = reverse("product-requests-report-damaged", args=[req.id])
    response = partner_client.post(url, {"damaged_quantity": 5})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_cannot_mark_already_received(partner_client, partner, product):
    req = ProductRequest.objects.create(product=product, quantity=3, user=partner, status='received')
    url = reverse("product-requests-mark-received", args=[req.id])
    response = partner_client.post(url, {})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_create_request_invalid_quantity(partner_client, product):
    url = reverse("product-requests-list")
    response_zero = partner_client.post(url, {"product": product.id, "quantity": 0, "for_store": False})
    response_negative = partner_client.post(url, {"product": product.id, "quantity": -5, "for_store": False})

    assert response_zero.status_code == status.HTTP_400_BAD_REQUEST
    assert response_negative.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_create_request_nonexistent_product(partner_client):
    url = reverse("product-requests-list")
    response = partner_client.post(url, {"product": 9999, "quantity": 1, "for_store": False})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_partner_cannot_access_other_request(partner_client, admin, product):
    req = ProductRequest.objects.create(product=product, quantity=2, user=admin, status='approved')
    url = reverse("product-requests-mark-received", args=[req.id])
    response = partner_client.post(url, {})
    assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]
