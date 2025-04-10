from datetime import date, timedelta
from django.urls import reverse
from rest_framework import status
import pytest
from apps.finance.models import FinanceEntry
from apps.products.models import PartnerProduct
from apps.products.models import Product
from apps.users.models import User
from apps.stores.models import City
from rest_framework.test import APIClient

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
    user.city = city
    user.save()
    return user


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
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def partner_client(partner_user):
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=partner_user)
    return client




@pytest.fixture
def product():
    return Product.objects.create(name="Товар X", price=100)


@pytest.fixture
def partner_product(partner_user, product):
    return PartnerProduct.objects.create(
        partner=partner_user,
        product=product,
        price=100.00,
        quantity=10,
        sold_quantity=2,
        damaged_quantity=1,
        bonus_quantity=1,
        returned_quantity=0
    )


@pytest.mark.django_db
def test_catalog_finance_basic_summary(partner_client, partner_product):
    url = reverse("finance:partner-catalog-finance")
    FinanceEntry.objects.create(
        user=partner_product.partner,
        date=date.today(),
        entry_type="sale",
        partner_product=partner_product,
        quantity=2,
        amount=200
    )
    response = partner_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["sales"]["amount"] == 200.0


@pytest.mark.django_db
def test_catalog_finance_date_filter(partner_client, partner_product):
    today = date.today()
    week_ago = today - timedelta(days=7)

    FinanceEntry.objects.create(
        user=partner_product.partner,
        date=week_ago,
        entry_type="sale",
        partner_product=partner_product,
        quantity=1,
        amount=100
    )

    FinanceEntry.objects.create(
        user=partner_product.partner,
        date=today,
        entry_type="sale",
        partner_product=partner_product,
        quantity=1,
        amount=100
    )

    url = reverse("finance:partner-catalog-finance")
    response = partner_client.get(url, {"from_date": today.isoformat()})
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["sales"]["amount"] == 100.0


@pytest.mark.django_db
def test_catalog_finance_profit_calculation(partner_client, partner_product):
    # Цены считаются автоматически в save()
    FinanceEntry.objects.create(user=partner_product.partner, date=date.today(), entry_type="sale", quantity=5, partner_product=partner_product)
    FinanceEntry.objects.create(user=partner_product.partner, date=date.today(), entry_type="return", quantity=1, partner_product=partner_product)
    FinanceEntry.objects.create(user=partner_product.partner, date=date.today(), entry_type="income", amount=100, partner_product=partner_product)
    FinanceEntry.objects.create(user=partner_product.partner, date=date.today(), entry_type="damage", quantity=1, partner_product=partner_product)
    FinanceEntry.objects.create(user=partner_product.partner, date=date.today(), entry_type="expense", amount=150, partner_product=partner_product)

    url = reverse("finance:partner-catalog-finance") + f"?partner_product_id={partner_product.id}"
    response = partner_client.get(url)
    data = response.json()

    print(data)
    assert response.status_code == status.HTTP_200_OK
    assert data["profit"] == 450.0




@pytest.mark.django_db
def test_catalog_finance_with_product_detail(partner_client, partner_product):
    url = reverse("finance:partner-catalog-finance")
    response = partner_client.get(url, {"partner_product_id": partner_product.id})
    data = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert "product_detail" in data
    assert data["product_detail"]["product_name"] == partner_product.product.name


@pytest.mark.django_db
def test_catalog_finance_product_not_found(partner_client):
    url = reverse("finance:partner-catalog-finance")
    response = partner_client.get(url, {"partner_product_id": 999})
    assert response.status_code == status.HTTP_200_OK
    assert "product_detail" not in response.json()


@pytest.mark.django_db
def test_catalog_finance_only_income_expense(partner_client, partner_user):
    FinanceEntry.objects.create(user=partner_user, date=date.today(), entry_type="income", amount=500)
    FinanceEntry.objects.create(user=partner_user, date=date.today(), entry_type="expense", amount=200)

    url = reverse("finance:partner-catalog-finance")
    response = partner_client.get(url)
    data = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert data["sales"]["amount"] == 0
    assert data["expenses"] == 200
    assert data["income"] == 500
    assert data["profit"] == 300


@pytest.mark.django_db
def test_catalog_finance_only_product_entries(partner_client, partner_product):
    FinanceEntry.objects.create(user=partner_product.partner, date=date.today(), entry_type="sale", quantity=2, partner_product=partner_product)
    FinanceEntry.objects.create(user=partner_product.partner, date=date.today(), entry_type="damage", quantity=1, partner_product=partner_product)

    url = reverse("finance:partner-catalog-finance")
    response = partner_client.get(url)
    data = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert data["income"] == 0
    assert data["expenses"] == 0
    assert data["sales"]["amount"] > 0
    assert data["damages"]["amount"] > 0


@pytest.mark.django_db
def test_catalog_finance_empty_period(partner_client, partner_product):
    FinanceEntry.objects.create(user=partner_product.partner, date=date.today(), entry_type="sale", quantity=1, partner_product=partner_product)

    past_date = (date.today() - timedelta(days=30)).isoformat()
    url = reverse("finance:partner-catalog-finance") + f"?from_date={past_date}&to_date={past_date}"
    response = partner_client.get(url)
    data = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert data["sales"]["amount"] == 0
    assert data["income"] == 0
    assert data["expenses"] == 0
    assert data["profit"] == 0


@pytest.mark.django_db
def test_catalog_finance_invalid_date_range(partner_client, partner_product):
    today = date.today().isoformat()
    url = reverse("finance:partner-catalog-finance") + f"?from_date={today}&to_date=2000-01-01"
    response = partner_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["profit"] == 0


@pytest.mark.django_db
def test_catalog_finance_foreign_product_id(partner_client, admin_user):
    FinanceEntry.objects.create(user=admin_user, date=date.today(), entry_type="sale", amount=999)

    url = reverse("finance:partner-catalog-finance") + f"?partner_product_id=999999"  # not existing
    response = partner_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert "product_detail" not in response.json()


@pytest.mark.django_db
def test_catalog_finance_small_and_large_amounts(partner_client, partner_product):
    FinanceEntry.objects.create(user=partner_product.partner, date=date.today(), entry_type="income", amount=0.01)
    FinanceEntry.objects.create(user=partner_product.partner, date=date.today(), entry_type="expense", amount=1_000_000)

    url = reverse("finance:partner-catalog-finance")
    response = partner_client.get(url)
    data = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert data["income"] == 0.01
    assert data["expenses"] == 1_000_000


@pytest.mark.django_db
def test_catalog_finance_duplicate_entries(partner_client, partner_product):
    for _ in range(3):
        FinanceEntry.objects.create(user=partner_product.partner, date=date.today(), entry_type="sale", quantity=1, partner_product=partner_product)

    url = reverse("finance:partner-catalog-finance")
    response = partner_client.get(url)
    data = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert data["sales"]["quantity"] == 3

