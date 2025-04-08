
from unittest.mock import patch
from apps.orders.models import ProductRequest
import pytest
from apps.users.models import User
from apps.stores.models import Store, City
from apps.products.models import Product, PartnerProduct

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
def city():
    return City.objects.create(name="Test City")

@pytest.fixture
def store(partner, city):
    return Store.objects.create(
        name="Test Store",
        inn="123456789012",
        address="Test Address",
        phone="+996777777777",
        city=city,
        creator=partner,
        is_active=True,
        status="approved"
    )

@pytest.fixture
def product():
    return Product.objects.create(
        name="Bonaqua",
        price=50,
        quantity=100,
        is_active=True,
        is_bonus_eligible=True
    )

@pytest.fixture
def partner_product(partner, product):
    return PartnerProduct.objects.create(
        partner=partner,
        product=product,
        quantity=30,
        bonus_quantity=5,
        price=50.0
    )


@pytest.mark.django_db
def test_signals_create_self_request(partner):
    product = Product.objects.create(name="Test", price=100, quantity=50, is_active=True)

    with patch("apps.finance.services.update_partner_daily_stats") as mock_update:
        req = ProductRequest.objects.create(
            product=product,
            user=partner,
            quantity=3,
            request_type='SELF',
            status='pending'
        )
        # используем фактическую дату
        expected_date = req.created_at.date()
        mock_update.assert_called_once_with(partner, expected_date)


@pytest.mark.django_db
def test_signals_create_store_request(partner, city):
    product = Product.objects.create(name="Test", price=100, quantity=50, is_active=True)
    partner_product = PartnerProduct.objects.create(
        partner=partner,
        product=product,
        quantity=10,
        price=100,
    )
    store = Store.objects.create(
        name="Store",
        city=city,
        inn="123456789012",
        address="123",
        phone="+996777777777",
        creator=partner,
        status="approved",
        is_active=True
    )

    with patch("apps.finance.services.update_partner_daily_stats") as mock_partner_update, \
         patch("apps.finance.services.update_store_daily_stats") as mock_store_update:

        req = ProductRequest.objects.create(
            product=product,
            user=partner,
            quantity=3,
            request_type='STORE',
            status='approved',
            partner_product=partner_product,
            store=store
        )

        expected_date = req.created_at.date()
        mock_partner_update.assert_called_once_with(partner, expected_date)
        mock_store_update.assert_called_once_with(store, expected_date)


@pytest.mark.django_db
def test_signals_status_change(partner):
    product = Product.objects.create(name="Test", price=100, quantity=50, is_active=True)

    req = ProductRequest.objects.create(
        product=product,
        user=partner,
        quantity=3,
        request_type='SELF',
        status='pending'
    )

    with patch("apps.finance.services.update_partner_daily_stats") as mock_update:
        req.status = "approved"
        req.save()

        expected_date = req.created_at.date()
        mock_update.assert_called_once_with(partner, expected_date)