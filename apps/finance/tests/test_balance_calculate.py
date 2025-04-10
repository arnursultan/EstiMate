import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from datetime import date

from apps.orders.models import ProductRequest
from apps.products.models import Product, PartnerProduct
from apps.users.models import User
from apps.stores.models import Store, City, StoreDebt
from apps.finance.models import PartnerFinanceStat, FinanceEntry


@pytest.fixture
def city():
    return City.objects.create(name="Город X")


@pytest.fixture
def store(city):
    return Store.objects.create(
        name="Магазин 1",
        city=city,
        inn="123456789012",
        address="ул. Тестовая",
        phone="700000000",
        status="approved",
        is_active=True,
    )


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(
        email="admin@example.com",
        phone="70000000001",
        password="adminpass",
        first_name="Админ",
        last_name="Админов"
    )


@pytest.fixture
def partner_user():
    return User.objects.create_user(
        email="partner@example.com",
        phone="70000000002",
        password="partnerpass",
        first_name="Партнёр",
        last_name="Тестович"
    )


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def partner_client(partner_user):
    client = APIClient()
    client.force_authenticate(user=partner_user)
    return client


@pytest.mark.django_db
def test_balance_as_admin(admin_client, partner_user, city, store):
    from apps.products.models import Product
    from apps.orders.models import ProductRequest
    from apps.stores.models import StoreDebt

    product = Product.objects.create(name="Товар", price=100, quantity=50)

    # Создание заявки с бонусом
    ProductRequest.objects.create(
        user=partner_user,
        product=product,
        store=store,
        quantity=10,
        bonus_quantity=2,
        status="approved"
    )

    # Долг
    StoreDebt.objects.create(store=store, amount=500, is_paid=False)

    url = reverse("finance:balance-calculator")
    response = admin_client.get(url)
    print(">>> RESPONSE JSON:", response.json())

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "total_balance" in data



@pytest.mark.django_db
def test_balance_as_partner_with_data(partner_user, partner_client):
    # Создаём статистику без свойств-property
    PartnerFinanceStat.objects.create(user=partner_user, date=date.today())

    url = reverse("finance:balance-calculator")
    response = partner_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert "total_balance" in response.json()  # damaged_loss + manual


@pytest.mark.django_db
def test_balance_invalid_date(partner_client):
    url = reverse("finance:balance-calculator")
    response = partner_client.get(url, {"date": "invalid-date"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "error" in response.data


@pytest.mark.django_db
def test_balance_with_debt_and_bonus(partner_client, partner_user, store):
    # 1. Продукт с бонусами
    product = Product.objects.create(
        name="Test Bonus Product",
        price=200.0,
        is_bonus_eligible=True
    )

    # 2. ProductRequest с бонусом (21 шт → 1 бонус)
    product_request = ProductRequest.objects.create(
        user=partner_user,
        product=product,
        quantity=21,
        status='received',
        request_type='SELF',
    )
    target_date = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)
    product_request.created_at = target_date
    product_request.save(update_fields=['created_at'])

    # 3. Расход
    FinanceEntry.objects.create(
        user=partner_user,
        store=store,
        amount=100.0,
        entry_type='expense',
        date=target_date.date()
    )

    # 4. Долг
    StoreDebt.objects.create(
        store=store,
        amount=50.0,
        created_at=target_date,
    )

    # 5. Запрос баланса
    url = reverse("finance:balance-calculator")
    response = partner_client.get(url, {'date': target_date.date().isoformat()})
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    print(">>> RESPONSE JSON:", data)

    # 6. Проверка значений
    components = data.get('balance_components', {})

    assert components.get('bonus_value') == 200.0, f"Expected bonus_value 200.0, got {components.get('bonus_value')}"
    assert components.get('expenses') == 100.0, f"Expected expenses 100.0, got {components.get('expenses')}"
    assert components.get('outstanding_debt') == 0.0, f"Expected debt 0.0, got {components.get('outstanding_debt')}"



@pytest.mark.django_db
def test_balance_empty_data_returns_zero(partner_client):
    url = reverse("finance:balance-calculator")
    response = partner_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    for val in response.data["balance_components"].values():
        assert val == 0 or val == 0.0

@pytest.mark.django_db
def test_bonus_not_eligible(partner_client, partner_user):
    product = Product.objects.create(name="No Bonus", price=100, is_bonus_eligible=False)
    ProductRequest.objects.create(user=partner_user, product=product, quantity=21, status='received', request_type='SELF')
    url = reverse("finance:balance-calculator")
    response = partner_client.get(url, {"date": timezone.now().date()})
    assert response.status_code == 200
    assert response.json()['balance_components']['bonus_value'] == 0


@pytest.mark.django_db
def test_paid_debt_counted(admin_client, store):
    paid_date = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)
    StoreDebt.objects.create(store=store, amount=150, is_paid=True, paid_at=paid_date)

    url = reverse("finance:balance-calculator")
    response = admin_client.get(url, {"date": paid_date.date().isoformat(), "store": store.id})

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['balance_components']['paid_debt'] == 150.0


@pytest.mark.django_db
def test_partner_sees_only_their_debts(partner_client, partner_user, store):
    other_store = store
    StoreDebt.objects.create(store=other_store, amount=999, is_paid=False)
    url = reverse("finance:balance-calculator")
    response = partner_client.get(url, {"date": timezone.now().date()})
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['balance_components']['outstanding_debt'] == 0


@pytest.mark.django_db
def test_invalid_date_format_returns_400(partner_client):
    url = reverse("finance:balance-calculator")
    response = partner_client.get(url, {"date": "not-a-date"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_admin_filters_by_city_and_store(admin_client, admin_user, store, city):
    today = timezone.now().date()
    product = Product.objects.create(name="Filtered Product", price=123, is_bonus_eligible=True)
    request = ProductRequest.objects.create(
        user=admin_user,
        product=product,
        quantity=21,
        status='received',
        request_type='SELF',
        store=store
    )
    request.created_at = timezone.now()
    request.bonus_quantity = 1
    request.save(update_fields=['created_at', 'bonus_quantity'])

    url = reverse("finance:balance-calculator")
    response = admin_client.get(url, {
        "date": today.isoformat(),
        "store": store.id,
        "city": city.id
    })
    assert response.status_code == status.HTTP_200_OK
    assert 'bonus_value' in response.json()['balance_components']

@pytest.mark.django_db
def test_bonus_not_counted_for_unapproved_statuses(partner_client, partner_user):
    product = Product.objects.create(name="P1", price=100, is_bonus_eligible=True)
    for status1 in ['pending', 'rejected']:
        ProductRequest.objects.create(
            user=partner_user,
            product=product,
            quantity=21,
            request_type='SELF',
            status=status1
        )
    url = reverse("finance:balance-calculator")
    response = partner_client.get(url, {'date': timezone.now().date().isoformat()})
    assert response.status_code == 200
    assert response.json()['balance_components']['bonus_value'] == 0


@pytest.mark.django_db
def test_balance_with_city_filter(admin_client, partner_user, store, city):
    # Привязка магазина к городу
    store.city = city
    store.save()

    # Продукт с бонусом
    product = Product.objects.create(name="CityProduct", price=100, is_bonus_eligible=True)
    partner_product = PartnerProduct.objects.create(partner=partner_user, product=product, quantity=100, price=100)

    # Запрос STORE-типа (только они видны по store → city)
    req = ProductRequest.objects.create(
        user=partner_user,
        product=product,
        store=store,
        partner_product=partner_product,
        quantity=21,
        status="received",
        request_type="STORE"
    )
    req.created_at = timezone.now()
    req.save(update_fields=['created_at'])

    url = reverse("finance:balance-calculator")
    response = admin_client.get(url, {
        'date': req.created_at.date().isoformat(),
        'city': city.id
    })

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data['balance_components']['bonus_value'] == 100.0


@pytest.mark.django_db
def test_balance_with_no_data_on_date(partner_client):
    url = reverse("finance:balance-calculator")
    response = partner_client.get(url, {'date': '1990-01-01'})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()['balance_components']
    assert data['bonus_value'] == 0
    assert data['income'] == 0
    assert data['expenses'] == 0


@pytest.mark.django_db
def test_zero_bonus_quantity_not_counted(partner_client, partner_user):
    product = Product.objects.create(name="NoBonus", price=100, is_bonus_eligible=True)
    req = ProductRequest.objects.create(
        user=partner_user,
        product=product,
        quantity=1,
        request_type="SELF",
        status="received",
        bonus_quantity=0
    )
    req.created_at = timezone.now()
    req.save()
    url = reverse("finance:balance-calculator")
    response = partner_client.get(url, {'date': req.created_at.date().isoformat()})
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['balance_components']['bonus_value'] == 0


@pytest.mark.django_db
def test_inactive_product_not_counted(partner_client, partner_user):
    product = Product.objects.create(
        name="Inactive Bonus",
        price=100,
        is_bonus_eligible=True,
        is_active=False
    )
    req = ProductRequest.objects.create(
        user=partner_user,
        product=product,
        quantity=21,
        status="received",
        request_type="SELF"
    )
    req.created_at = timezone.now()
    req.save()
    url = reverse("finance:balance-calculator")
    response = partner_client.get(url, {'date': req.created_at.date().isoformat()})
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['balance_components']['bonus_value'] == 0
