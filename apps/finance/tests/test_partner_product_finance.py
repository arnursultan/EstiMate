import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.products.models import Product, PartnerProduct
from apps.stores.models import City

User = get_user_model()


@pytest.fixture
def city():
    return City.objects.create(name="Алматы")


@pytest.fixture
def partner_user(city):
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
def product():
    return Product.objects.create(name="Товар X", price=100.0, quantity=100, is_active=True)


@pytest.fixture
def partner_product(partner_user, product):
    return PartnerProduct.objects.create(
        partner=partner_user,
        product=product,
        price=100.0,
        quantity=10,
        sold_quantity=5,
        damaged_quantity=1,
        bonus_quantity=0,
        returned_quantity=0
    )


@pytest.mark.django_db
def test_create_sale_entry(partner_client, partner_product):
    url = reverse("finance:partner-product-finance")
    response = partner_client.post(url, {
        "partner_product_id": partner_product.id,
        "entry_type": "sale",
        "quantity": 3
    })
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_create_damage_entry(partner_client, partner_product):
    url = reverse("finance:partner-product-finance")
    response = partner_client.post(url, {
        "partner_product_id": partner_product.id,
        "entry_type": "damage",
        "quantity": 2
    })
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_create_return_entry(partner_client, partner_product):
    url = reverse("finance:partner-product-finance")
    response = partner_client.post(url, {
        "partner_product_id": partner_product.id,
        "entry_type": "return",
        "quantity": 2
    })
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_sale_exceeds_remaining(partner_client, partner_product):
    url = reverse("finance:partner-product-finance")
    response = partner_client.post(url, {
        "partner_product_id": partner_product.id,
        "entry_type": "sale",
        "quantity": 999
    })
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "quantity" in response.json()


@pytest.mark.django_db
def test_return_exceeds_sold(partner_client, partner_product):
    url = reverse("finance:partner-product-finance")
    response = partner_client.post(url, {
        "partner_product_id": partner_product.id,
        "entry_type": "return",
        "quantity": 99
    })
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "quantity" in response.json()


@pytest.mark.django_db
def test_sale_without_product_id(partner_client):
    url = reverse("finance:partner-product-finance")
    response = partner_client.post(url, {
        "entry_type": "sale",
        "quantity": 3
    })
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "partner_product_id" in response.json()


@pytest.mark.django_db
def test_foreign_partner_product_forbidden(partner_client, product):
    other_user = User.objects.create_user(
        email="foreign@example.com",
        phone="+77002223344",
        first_name="Чужой",
        last_name="Партнёр",
        password="pass123",
        role="partner"
    )
    foreign_product = PartnerProduct.objects.create(
        partner=other_user, product=product, price=100.0, quantity=10
    )

    url = reverse("finance:partner-product-finance")
    response = partner_client.post(url, {
        "partner_product_id": foreign_product.id,
        "entry_type": "sale",
        "quantity": 1
    })
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "partner_product_id" in response.json()


@pytest.mark.django_db
def test_income_with_quantity_fails(partner_client, partner_product):
    url = reverse("finance:partner-product-finance")
    response = partner_client.post(url, {
        "entry_type": "income",
        "amount": 100,
        "quantity": 2,
        "partner_product_id": partner_product.id
    })
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "quantity" in response.json()


@pytest.mark.django_db
def test_income_with_zero_amount(partner_client, partner_product):
    url = reverse("finance:partner-product-finance")
    response = partner_client.post(url, {
        "entry_type": "income",
        "amount": 0,
        "partner_product_id": partner_product.id
    })
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "amount" in response.json()



@pytest.mark.django_db
def test_unauthenticated_user_cannot_post():
    client = APIClient()
    url = reverse("finance:partner-product-finance")
    response = client.post(url, {})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_create_expense_entry_success(partner_client, partner_product):
    url = reverse("finance:partner-product-finance")
    response = partner_client.post(url, {
        "partner_product_id": partner_product.id,
        "entry_type": "expense",
        "amount": 150,
        "note": "транспортировка"
    })
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["entry_type"] == "expense"
    assert data["amount"] == "150.00"
    assert data["note"] == "транспортировка"



@pytest.mark.django_db
def test_optional_note_field(partner_client, partner_product):
    url = reverse("finance:partner-product-finance")
    response = partner_client.post(url, {
        "partner_product_id": partner_product.id,
        "entry_type": "sale",
        "quantity": 1
    })
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["note"] == ""


@pytest.mark.django_db
def test_double_sale_reduces_remaining(partner_client, partner_product):
    url = reverse("finance:partner-product-finance")

    # Первый sale
    resp1 = partner_client.post(url, {
        "partner_product_id": partner_product.id,
        "entry_type": "sale",
        "quantity": 1
    })
    assert resp1.status_code == status.HTTP_201_CREATED

    # Обновляем продукт
    partner_product.refresh_from_db()

    # Второй sale превышает остаток
    resp2 = partner_client.post(url, {
        "partner_product_id": partner_product.id,
        "entry_type": "sale",
        "quantity": partner_product.remaining_quantity + 1
    })
    assert resp2.status_code == status.HTTP_400_BAD_REQUEST
    assert "quantity" in resp2.json()
