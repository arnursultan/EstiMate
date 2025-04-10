import pytest
from rest_framework.test import APIClient
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.finance.models import InventorySummary
from datetime import date, timedelta
from rest_framework import status

from apps.products.models import Product, PartnerProduct

User = get_user_model()

# --- Фикстуры ---


@pytest.fixture
def product():
    return Product.objects.create(
        name="Товар A", price=100, quantity=100, is_active=True
    )

@pytest.fixture
def partner_product(partner_user, product):
    return PartnerProduct.objects.create(
    partner=partner_user,
    product=product,
    price=100,
    quantity=10,
    sold_quantity=2,
    damaged_quantity=1,
    bonus_quantity=1,
    returned_quantity=0
)


@pytest.fixture
def partner_user(db):
    return User.objects.create_user(
        email="partner@example.com",
        phone="+77001112233",
        first_name="Партнёр",
        last_name="Тестович",
        password="testpass123",
        role="partner",
    )

@pytest.fixture
def partner_client(partner_user):
    client = APIClient()
    client.force_authenticate(user=partner_user)
    return client

@pytest.fixture
def inventory_summary(partner_user):
    # Самый свежий, чтобы generate_inventory_summary() его нашёл
    return InventorySummary.objects.create(
        user=partner_user,
        date=date.today(),
        total_quantity=100,
        total_sold=20,
        total_damaged=5,
        total_bonus=10,
        total_returned=2,
        total_remaining=63,
        total_value=10000,
        total_sold_value=2000,
        total_damaged_value=500,
        total_bonus_value=1000,
        total_remaining_value=6300,
        data={"Товар А": {"remaining": 10, "sold": 2}}
    )

# --- Тесты ---

@pytest.mark.django_db
def test_inventory_view_requires_authentication():
    url = reverse("finance:inventory-summary")
    client = APIClient()
    response = client.get(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.django_db
def test_inventory_summary_success(partner_client, partner_user, partner_product):
    from apps.finance.views import generate_inventory_summary
    generate_inventory_summary(partner_user)  # принудительно сгенерируем объект

    url = reverse("finance:inventory-summary")
    response = partner_client.get(url)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    print(data)
    assert data["user_name"] == "Партнёр Тестович"
    assert data["total_quantity"] == 10
    assert data["total_sold"] == 2
    assert float(data["total_remaining_value"]) == partner_product.remaining_quantity * partner_product.price
    assert "products" in data["data"]

@pytest.mark.django_db
def test_inventory_summary_empty(partner_client, partner_user):
    # На всякий случай удалим все записи
    InventorySummary.objects.filter(user=partner_user).delete()

    url = reverse("finance:inventory-summary")
    response = partner_client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["message"] == "В вашем каталоге нет товаров"


@pytest.mark.django_db
def test_inventory_aggregation_multiple_products(partner_client, partner_user):
    product1 = Product.objects.create(name="Товар A", price=100, quantity=0, is_active=True)
    product2 = Product.objects.create(name="Товар B", price=200, quantity=0, is_active=True)

    PartnerProduct.objects.create(
        partner=partner_user, product=product1, price=100,
        quantity=5, sold_quantity=1, damaged_quantity=1, bonus_quantity=0, returned_quantity=0
    )
    PartnerProduct.objects.create(
        partner=partner_user, product=product2, price=200,
        quantity=3, sold_quantity=1, damaged_quantity=0, bonus_quantity=1, returned_quantity=1
    )

    from apps.finance.views import generate_inventory_summary
    generate_inventory_summary(partner_user)

    url = reverse("finance:inventory-summary")
    response = partner_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["total_quantity"] == 8
    assert data["total_sold"] == 2
    assert data["total_damaged"] == 1
    assert data["total_bonus"] == 1
    assert data["total_remaining"] == 5
    assert float(data["total_remaining_value"]) == 700.0



@pytest.mark.django_db
def test_inventory_summary_updates_old_record(partner_client, partner_user):
    old_date = date.today() - timedelta(days=2)
    InventorySummary.objects.create(
        user=partner_user, date=old_date,
        total_quantity=1, total_remaining=1, total_value=100,
        total_sold=0, total_damaged=0, total_bonus=0,
        total_returned=0, total_remaining_value=100,
        total_sold_value=0, total_damaged_value=0,
        total_bonus_value=0, data={"products": []}
    )

    product = Product.objects.create(name="Товар X", price=300, quantity=0, is_active=True)
    PartnerProduct.objects.create(
        partner=partner_user, product=product, price=300,
        quantity=4, sold_quantity=1, damaged_quantity=1, bonus_quantity=0, returned_quantity=0
    )

    from apps.finance.views import generate_inventory_summary
    summary = generate_inventory_summary(partner_user)

    url = reverse("finance:inventory-summary")
    response = partner_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert summary.date == date.today()
    assert data["total_quantity"] == 4
    assert data["total_remaining"] == 2
    assert float(data["total_remaining_value"]) == 600.0

