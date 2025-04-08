import pytest
from django.urls import reverse
from rest_framework import status
from apps.orders.models import ProductRequest
from decimal import Decimal
from rest_framework.test import APIClient

from apps.stores.models import StoreDebt
from apps.users.models import User


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
def partner_client(partner):
    client = APIClient()
    client.force_authenticate(user=partner)
    return client


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
def admin_client(admin):
    client = APIClient()
    client.force_authenticate(user=admin)
    return client


@pytest.fixture
def city():
    from apps.stores.models import City
    return City.objects.create(name="Bishkek")


@pytest.fixture
def store(partner, city):
    from apps.stores.models import Store
    return Store.objects.create(
        name="Test Store",
        inn="123456789012",
        address="Main St",
        phone="+996777777777",
        city=city,
        creator=partner,
        is_active=True,
        status="approved"
    )


@pytest.fixture
def product():
    from apps.products.models import Product
    return Product.objects.create(
        name="Bonaqua",
        price=100,
        quantity=100,
        is_active=True
    )


@pytest.fixture
def partner_product(partner, product):
    from apps.products.models import PartnerProduct
    return PartnerProduct.objects.create(
        partner=partner,
        product=product,
        quantity=10,
        bonus_quantity=0,
        price=100.0
    )



@pytest.mark.django_db
def test_pay_debt_success_full(partner_client, store, partner_product):
    product_request = ProductRequest.objects.create(
        product=partner_product.product,
        user=partner_product.partner,
        quantity=3,
        request_type="STORE",
        store=store,
        partner_product=partner_product,
        status="approved",
        total_price=300
    )
    StoreDebt.objects.create(
        store=store,
        amount=Decimal("300.00"),
        request=product_request,
        created_by=partner_product.partner
    )
    url = reverse("pay-debt")
    data = {"store_id": store.id, "amount": 300}
    response = partner_client.post(url, data)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["paid_amount"] == 300
    assert response.data["remaining_debt"] == 0


@pytest.mark.django_db
def test_pay_debt_partial_payment(partner_client, store, partner_product):
    pr = ProductRequest.objects.create(
        product=partner_product.product,
        user=partner_product.partner,
        quantity=2,
        request_type="STORE",
        store=store,
        partner_product=partner_product,
        status="approved",
        total_price=200
    )
    StoreDebt.objects.create(
        store=store,
        amount=Decimal("200.00"),
        request=pr,
        created_by=partner_product.partner
    )
    url = reverse("pay-debt")
    data = {"store_id": store.id, "amount": 50}
    response = partner_client.post(url, data)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["paid_amount"] == 50
    assert response.data["remaining_debt"] == 150


@pytest.mark.django_db
def test_pay_debt_amount_exceeds(partner_client, store, partner_product):
    pr = ProductRequest.objects.create(
        product=partner_product.product,
        user=partner_product.partner,
        quantity=1,
        request_type="STORE",
        store=store,
        partner_product=partner_product,
        status="approved",
        total_price=100
    )
    StoreDebt.objects.create(
        store=store,
        amount=Decimal("100.00"),
        request=pr,
        created_by=partner_product.partner
    )
    url = reverse("pay-debt")
    data = {"store_id": store.id, "amount": 150}
    response = partner_client.post(url, data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "превышает общий долг" in str(response.data["error"])


@pytest.mark.django_db
def test_pay_debt_no_debts(partner_client, store, partner_product):
    # Добавим ProductRequest, чтобы пройти проверку прав
    ProductRequest.objects.create(
        product=partner_product.product,
        user=partner_product.partner,
        quantity=2,
        request_type="STORE",
        store=store,
        partner_product=partner_product,
        status="approved"
    )

    url = reverse("pay-debt")
    data = {"store_id": store.id, "amount": 100}
    response = partner_client.post(url, data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "нет неоплаченных долгов" in str(response.data["error"])



@pytest.mark.django_db
def test_pay_debt_invalid_store(partner_client):
    url = reverse("pay-debt")
    data = {"store_id": 9999, "amount": 100}
    response = partner_client.post(url, data)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "не найден" in str(response.data["error"])


@pytest.mark.django_db
def test_pay_debt_no_access(admin_client, store):
    url = reverse("pay-debt")
    data = {"store_id": store.id, "amount": 100}
    response = admin_client.post(url, data)


    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "нет неоплаченных долгов" in str(response.data["error"])



@pytest.mark.django_db
def test_pay_debt_invalid_data(partner_client):
    url = reverse("pay-debt")
    response = partner_client.post(url, {"store_id": "", "amount": ""})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "указать store_id и amount" in str(response.data["error"])
