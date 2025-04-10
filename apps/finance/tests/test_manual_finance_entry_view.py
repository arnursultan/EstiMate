from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.stores.models import Store, City
from apps.products.models import Product
from apps.orders.models import PartnerProduct


# === FIXTURES ===

@pytest.fixture
def city():
    return City.objects.create(name="Тестовый город")

@pytest.fixture
def store(city):
    return Store.objects.create(
        name="Тестовый магазин",
        city=city,
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
def partner_product(partner_user, store, product):
    partner_product = PartnerProduct.objects.create(
        product=product,
        price=100,
        quantity=10,  # Начальное количество
        sold_quantity=5,
        partner=partner_user
    )
    partner_product.update_quantity(10, operation='add')  # Пример добавления количества
    return partner_product

@pytest.fixture
def finance_entry_data(partner_user, store, partner_product):
    return {
        "entry_type": "sale",
        "amount": 500,
        "quantity": 5,
        "store": store.id,
        "partner_product": partner_product.id,
        "note": "Test sale"
    }

# === TESTS ===

@pytest.mark.django_db
def test_create_finance_entry(admin_client, partner_product, partner_user, store):
    finance_entry_data = {
        "entry_type": "sale",
        "amount": 100,
        "quantity": 5,
        "store": store.id,
        "partner_product": partner_product.id,
        "note": "Test sale",
        "date": timezone.now().date().isoformat()  # 👈 добавили поле date
    }

    url = reverse("finance:manual-finance")
    response = admin_client.post(url, finance_entry_data, format='json')

    print(">>> RESPONSE DATA:", response.json())  # можно оставить для отладки

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["entry_type"] == "sale"
    assert Decimal(data["amount"]) == Decimal("500.00")
    assert data["quantity"] == 5

@pytest.mark.django_db
def test_create_finance_entry_invalid_entry_type(partner_client, finance_entry_data):
    finance_entry_data["entry_type"] = "invalid_type"  # Неизвестный тип
    url = reverse("finance:manual-finance")
    response = partner_client.post(url, finance_entry_data, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "entry_type" in response.json()

@pytest.mark.django_db
def test_create_finance_entry_missing_partner_product(partner_client, store):
    data = {
        "entry_type": "sale",
        "quantity": 3,
        "amount": 100,
        "store": store.id,
        "note": "Без partner_product",
        "date": timezone.now().date().isoformat()
    }

    url = reverse("finance:manual-finance")
    response = partner_client.post(url, data, format='json')
    print(">>> RESPONSE:", response.json())
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "partner_product" in response.json()

@pytest.mark.django_db
def test_create_finance_entry_invalid_quantity(partner_client, partner_product, store):
    data = {
        "entry_type": "sale",
        "quantity": 0,
        "amount": 100,
        "store": store.id,
        "partner_product": partner_product.id,
        "note": "0 quantity",
        "date": timezone.now().date().isoformat()
    }

    url = reverse("finance:manual-finance")
    response = partner_client.post(url, data, format='json')
    print(">>> RESPONSE:", response.json())
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "quantity" in response.json()

@pytest.mark.django_db
def test_create_finance_entry_quantity_exceeds_available(partner_client, partner_product, store):
    data = {
        "entry_type": "sale",
        "quantity": 20,  # больше остатка
        "amount": 100,
        "store": store.id,
        "partner_product": partner_product.id,
        "note": "Too many",
        "date": timezone.now().date().isoformat()
    }

    url = reverse("finance:manual-finance")
    response = partner_client.post(url, data, format='json')
    print(">>> RESPONSE:", response.json())
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "quantity" in response.json()

@pytest.mark.django_db
def test_create_finance_entry_not_authorized_to_access_product(partner_client, finance_entry_data):
    finance_entry_data["partner_product"] = 9999  # Не существующий partner_product
    url = reverse("finance:manual-finance")
    response = partner_client.post(url, finance_entry_data, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "partner_product" in response.json()

@pytest.mark.django_db
def test_create_expense_or_income_invalid_amount(partner_client, store):
    data = {
        "entry_type": "income",
        "amount": 0,  # неверная сумма
        "store": store.id,
        "note": "Bad amount",
        "date": timezone.now().date().isoformat()
    }

    url = reverse("finance:manual-finance")
    response = partner_client.post(url, data, format='json')
    print(">>> RESPONSE:", response.json())
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "amount" in response.json()

@pytest.mark.django_db
def test_create_finance_entry_with_valid_amount_and_type(admin_client, store):
    data = {
        "entry_type": "income",
        "amount": 1234.56,
        "store": store.id,
        "note": "Valid income",
        "date": timezone.now().date().isoformat()
    }

    url = reverse("finance:manual-finance")
    response = admin_client.post(url, data, format='json')
    print(">>> RESPONSE:", response.json())
    assert response.status_code == status.HTTP_201_CREATED
    assert Decimal(response.json()["amount"]) == Decimal("1234.56")


@pytest.mark.django_db
def test_create_finance_entry_with_other_users_product(partner_client, admin_user, product, store):
    foreign_product = PartnerProduct.objects.create(
        partner=admin_user,  # чужой партнёр
        product=product,
        price=100,
        quantity=5
    )

    data = {
        "entry_type": "sale",
        "amount": 100,
        "quantity": 2,
        "store": store.id,
        "partner_product": foreign_product.id,
        "note": "Чужой товар",
        "date": timezone.now().date().isoformat()
    }

    url = reverse("finance:manual-finance")
    response = partner_client.post(url, data, format='json')
    print(">>> foreign product access:", response.json())
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "partner_product" in response.json()


# 2. Ошибка: возврат больше проданного
@pytest.mark.django_db
def test_return_more_than_sold(partner_client, partner_product, store):
    data = {
        "entry_type": "return",
        "amount": 0,
        "quantity": partner_product.sold_quantity + 1,  # больше чем sold_quantity
        "store": store.id,
        "partner_product": partner_product.id,
        "note": "Невозможный возврат",
        "date": timezone.now().date().isoformat()
    }

    url = reverse("finance:manual-finance")
    response = partner_client.post(url, data, format='json')
    print(">>> return too much:", response.json())
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "quantity" in response.json()


# 3. Успешный расход
@pytest.mark.django_db
def test_create_expense_success(partner_client, store):
    data = {
        "entry_type": "expense",
        "amount": 345.67,
        "store": store.id,
        "note": "Транспорт",
        "date": timezone.now().date().isoformat()
    }

    url = reverse("finance:manual-finance")
    response = partner_client.post(url, data, format='json')
    print(">>> expense:", response.json())
    assert response.status_code == status.HTTP_201_CREATED
    assert Decimal(response.json()["amount"]) == Decimal("345.67")


# 4. Ошибка: damage больше остатка
@pytest.mark.django_db
def test_damage_more_than_available(partner_client, partner_product, store):
    data = {
        "entry_type": "damage",
        "quantity": partner_product.remaining_quantity + 1,  # превышаем
        "amount": 0,
        "store": store.id,
        "partner_product": partner_product.id,
        "note": "Слишком много брака",
        "date": timezone.now().date().isoformat()
    }

    url = reverse("finance:manual-finance")
    response = partner_client.post(url, data, format='json')
    print(">>> damage too much:", response.json())
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "quantity" in response.json()


# 5. Ошибка: неизвестный entry_type
@pytest.mark.django_db
def test_invalid_entry_type(partner_client, store):
    data = {
        "entry_type": "abracadabra",
        "amount": 100,
        "store": store.id,
        "note": "Магия",
        "date": timezone.now().date().isoformat()
    }

    url = reverse("finance:manual-finance")
    response = partner_client.post(url, data, format='json')
    print(">>> invalid entry_type:", response.json())
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "entry_type" in response.json()
