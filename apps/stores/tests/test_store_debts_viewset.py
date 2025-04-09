import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from apps.users.models import User
from apps.products.models import Product
from apps.orders.models import ProductRequest
from apps.stores.models import Store, City, StoreDebt
from decimal import Decimal
from datetime import  timedelta
from rest_framework import status
from django.urls import reverse

@pytest.fixture
def partner_user():
    return User.objects.create_user(
        email="partner@example.com",
        phone="+996500000000",
        first_name="Partner",
        last_name="User",
        password="testpass123"
    )


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(
        email="admin@example.com",
        phone="+996700000000",
        first_name="Admin",
        last_name="User",
        password="adminpass123"
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
def city():
    return City.objects.create(name="Test City")


@pytest.fixture
def store(city, partner_user):
    return Store.objects.create(
        name="Test Store",
        city=city,
        inn="123456789012",
        address="Test Address",
        phone="+996555000000",
        creator=partner_user,
        status="approved",
        is_active=True
    )


@pytest.fixture
def product():
    return Product.objects.create(
        name="Test Product",
        price=Decimal("100.00"),
        quantity=100,
        is_active=True
    )


@pytest.fixture
def product_request(store, product, partner_user):
    return ProductRequest.objects.create(
        product=product,
        user=partner_user,
        quantity=5,
        request_type='STORE',
        status='approved',
        store=store
    )


@pytest.fixture
def store_debt(store, partner_user, product_request):
    return StoreDebt.objects.create(
        store=store,
        amount=Decimal("500.00"),
        created_by=partner_user,
        request=product_request
    )


@pytest.fixture
def paid_store_debt(store, partner_user, product_request):
    return StoreDebt.objects.create(
        store=store,
        amount=Decimal("300.00"),
        created_by=partner_user,
        request=product_request,
        is_paid=True,
        paid_at=timezone.now() - timedelta(days=1)
    )



@pytest.mark.django_db
def test_admin_can_list_all_debts(admin_client, store, product_request):
    StoreDebt.objects.create(store=store, amount=500, request=product_request)
    url = reverse('store-debt-list')
    response = admin_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1


@pytest.mark.django_db
def test_partner_can_only_see_own_store_debts(partner_client, store, product_request):
    StoreDebt.objects.create(store=store, amount=1000, request=product_request)
    url = reverse('store-debt-list')
    response = partner_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]['amount'] == '1000.00'


@pytest.mark.django_db
def test_partner_cannot_see_foreign_debt(partner_client, store, product_request, admin_user):
    # Долг чужого магазина
    foreign_debt = StoreDebt.objects.create(
        store=store, amount=1000, request=product_request
    )
    foreign_debt.request.user = admin_user
    foreign_debt.request.save()

    url = reverse('store-debt-list')
    response = partner_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 0


@pytest.mark.django_db
def test_admin_can_mark_debt_as_paid(admin_client, store, product_request):
    debt = StoreDebt.objects.create(store=store, amount=900, request=product_request)
    url = reverse('store-debt-mark-as-paid', args=[debt.id])
    response = admin_client.post(url, data={'is_paid': True})
    assert response.status_code == status.HTTP_200_OK
    debt.refresh_from_db()
    assert debt.is_paid is True
    assert debt.paid_at is not None


@pytest.mark.django_db
def test_partner_cannot_mark_debt_as_paid(partner_client, store, product_request):
    debt = StoreDebt.objects.create(store=store, amount=500, request=product_request)
    url = reverse('store-debt-mark-as-paid', args=[debt.id])
    response = partner_client.post(url, data={'is_paid': True})
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_partner_can_pay_debt_fully(partner_client, store, product_request):
    debt = StoreDebt.objects.create(store=store, amount=1000, request=product_request)
    url = reverse('store-debt-pay-debt')
    data = {
        'debt_id': debt.id,
        'payment_amount': '1000.00'
    }
    response = partner_client.post(url, data=data)
    assert response.status_code == status.HTTP_200_OK
    debt.refresh_from_db()
    assert debt.is_paid is True


@pytest.mark.django_db
def test_partner_can_pay_debt_partially(partner_client, store, product_request):
    debt = StoreDebt.objects.create(store=store, amount=1000, request=product_request)
    url = reverse('store-debt-pay-debt')
    data = {
        'debt_id': debt.id,
        'payment_amount': '600.00'
    }
    response = partner_client.post(url, data=data)
    assert response.status_code == status.HTTP_200_OK
    assert response.data['status'] == 'partial_payment'
    debt.refresh_from_db()
    assert debt.is_paid is True

    # проверим, что создался новый долг
    remaining_debt = StoreDebt.objects.filter(store=store, is_paid=False).first()
    assert remaining_debt.amount == 400


@pytest.mark.django_db
def test_cannot_pay_negative_amount(partner_client, store, product_request):
    debt = StoreDebt.objects.create(store=store, amount=1000, request=product_request)
    url = reverse('store-debt-pay-debt')
    data = {
        'debt_id': debt.id,
        'payment_amount': '-100.00'
    }
    response = partner_client.post(url, data=data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'payment_amount' in response.data


@pytest.mark.django_db
def test_cannot_pay_already_paid_debt(partner_client, store, product_request):
    debt = StoreDebt.objects.create(
        store=store,
        amount=500,
        is_paid=True,
        paid_at=timezone.now(),
        request=product_request
    )
    url = reverse('store-debt-pay-debt')
    data = {
        'debt_id': debt.id,
        'payment_amount': '500.00'
    }
    response = partner_client.post(url, data=data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'debt_id' in response.data
    assert 'уже погашен' in str(response.data['debt_id'][0])


@pytest.mark.django_db
def test_admin_cannot_mark_already_paid_debt(admin_client, store, product_request):
    debt = StoreDebt.objects.create(
        store=store, amount=300, is_paid=True, paid_at=timezone.now(), request=product_request
    )
    url = reverse('store-debt-mark-as-paid', args=[debt.id])
    response = admin_client.post(url, data={'is_paid': True})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    # response.data — это список ошибок
    assert isinstance(response.data, list)
    assert 'уже отмечен как оплаченный' in str(response.data[0])



@pytest.mark.django_db
def test_admin_cannot_mark_debt_as_unpaid(admin_client, store, product_request):
    debt = StoreDebt.objects.create(store=store, amount=300, request=product_request)
    url = reverse('store-debt-mark-as-paid', args=[debt.id])
    response = admin_client.post(url, data={'is_paid': False})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'is_paid' in response.data
    assert 'только отметить долг как оплаченный' in str(response.data['is_paid'][0])


@pytest.mark.django_db
def test_partner_cannot_pay_foreign_debt(partner_client, store, product_request, admin_user):
    foreign_debt = StoreDebt.objects.create(store=store, amount=700, request=product_request)
    foreign_debt.request.user = admin_user
    foreign_debt.request.save()

    url = reverse('store-debt-pay-debt')
    data = {
        'debt_id': foreign_debt.id,
        'payment_amount': '700.00'
    }
    response = partner_client.post(url, data=data)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert 'error' in response.data


@pytest.mark.django_db
def test_pay_debt_nonexistent_id(partner_client):
    url = reverse('store-debt-pay-debt')
    data = {
        'debt_id': 9999,
        'payment_amount': '100.00'
    }
    response = partner_client.post(url, data=data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'debt_id' in response.data
    assert 'не найден' in str(response.data['debt_id'][0])