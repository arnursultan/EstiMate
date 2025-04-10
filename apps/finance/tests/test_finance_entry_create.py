import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.products.models import Product, PartnerProduct
from datetime import date


@pytest.fixture
def partner_user():
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
def partner_product(partner_user):
    product = Product.objects.create(name="Товар X", price=100, quantity=0, is_active=True)
    return PartnerProduct.objects.create(
        partner=partner_user,
        product=product,
        price=100,
        quantity=10,
        sold_quantity=5,
        damaged_quantity=1,
        bonus_quantity=0,
        returned_quantity=2
    )


@pytest.mark.django_db
def test_create_income_entry(partner_client):
    url = reverse("finance:finance-entry-create")
    data = {
        "entry_type": "income",
        "amount": 500,
        "date": date.today().isoformat()
    }
    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["entry_type"] == "income"


@pytest.mark.django_db
def test_create_expense_entry(partner_client):
    url = reverse("finance:finance-entry-create")
    data = {
        "entry_type": "expense",
        "amount": 200,
        "date": date.today().isoformat()
    }
    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["entry_type"] == "expense"


@pytest.mark.django_db
def test_error_negative_amount_income(partner_client):
    url = reverse("finance:finance-entry-create")
    data = {
        "entry_type": "income",
        "amount": -100,
        "date": date.today().isoformat()
    }
    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_create_sale_entry(partner_client, partner_product):
    url = reverse("finance:finance-entry-create")
    data = {
        "entry_type": "sale",
        "quantity": 2,
        "partner_product": partner_product.id,
        "date": date.today().isoformat()
    }
    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["quantity"] == 2


@pytest.mark.django_db
def test_error_sale_without_product(partner_client):
    url = reverse("finance:finance-entry-create")
    data = {
        "entry_type": "sale",
        "quantity": 2,
        "date": date.today().isoformat()
    }
    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_error_sale_insufficient_quantity(partner_client, partner_product):
    partner_product.quantity = 5
    partner_product.sold_quantity = 3
    partner_product.damaged_quantity = 1
    partner_product.bonus_quantity = 0
    partner_product.returned_quantity = 0
    partner_product.save()

    url = reverse("finance:finance-entry-create")
    data = {
        "entry_type": "sale",
        "quantity": 5,
        "partner_product": partner_product.id,
        "date": date.today().isoformat()
    }
    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "quantity" in response.json()



@pytest.mark.django_db
def test_create_damage_entry(partner_client, partner_product):
    url = reverse("finance:finance-entry-create")
    data = {
        "entry_type": "damage",
        "quantity": 1,
        "partner_product": partner_product.id,
        "date": date.today().isoformat()
    }
    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_create_return_entry(partner_client, partner_product):
    url = reverse("finance:finance-entry-create")
    data = {
        "entry_type": "return",
        "quantity": 1,
        "partner_product": partner_product.id,
        "date": date.today().isoformat()
    }
    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_error_return_exceeds_sold(partner_client, partner_product):
    url = reverse("finance:finance-entry-create")
    data = {
        "entry_type": "return",
        "quantity": 10,
        "partner_product": partner_product.id,
        "date": date.today().isoformat()
    }
    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_error_accessing_foreign_product(partner_client):
    other_user = User.objects.create_user(
        email="foreign@example.com",
        phone="+77777777777",
        first_name="Иван",
        last_name="Чужой",
        password="12345678"
    )
    product = Product.objects.create(name="Чужой товар", price=50)
    foreign_pp = PartnerProduct.objects.create(partner=other_user, product=product, price=50, quantity=5)

    url = reverse("finance:finance-entry-create")
    data = {
        "entry_type": "sale",
        "quantity": 1,
        "partner_product": foreign_pp.id,
        "date": date.today().isoformat()
    }
    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_authentication_required():
    url = reverse("finance:finance-entry-create")
    client = APIClient()
    data = {
        "entry_type": "income",
        "amount": 100,
        "date": date.today().isoformat()
    }
    response = client.post(url, data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_sale_without_partner_product(partner_client):
    url = reverse("finance:finance-entry-create")
    data = {
        "entry_type": "sale",
        "quantity": 3,
        "date": date.today().isoformat()
    }
    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "partner_product" in response.json()


@pytest.mark.django_db
def test_quantity_set_for_income(partner_client):
    url = reverse("finance:finance-entry-create")
    data = {
        "entry_type": "income",
        "amount": 300,
        "quantity": 2,  # должно быть запрещено
        "date": date.today().isoformat()
    }
    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "quantity" in response.json()


@pytest.mark.django_db
def test_income_with_zero_amount(partner_client):
    url = reverse("finance:finance-entry-create")
    data = {
        "entry_type": "income",
        "amount": 0,
        "date": date.today().isoformat()
    }
    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "amount" in response.json()


@pytest.mark.django_db
def test_return_without_quantity(partner_client, partner_product):
    url = reverse("finance:finance-entry-create")
    data = {
        "entry_type": "return",
        "partner_product": partner_product.id,
        "date": date.today().isoformat()
    }
    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "quantity" in response.json()
