import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.stores.models import Store, StoreDebt, City
from apps.users.models import User


@pytest.fixture
def partner_user():
    return User.objects.create_user(
        email="partner@example.com",
        password="Partner123",
        phone="+996700000002",
        first_name="Partner",
        last_name="User",
        status="approved"
    )


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(
        email="admin@example.com",
        password="Admin123",
        phone="+996700000001",
        first_name="Admin",
        last_name="User"
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
    return City.objects.create(name="Bishkek")


@pytest.fixture
def store(city, partner_user):
    return Store.objects.create(
        name="Partner Store",
        inn="1234567890",
        city=city,
        address="Main St",
        phone="+996700000010",
        status="approved",
        is_active=True
    )


@pytest.mark.django_db
def test_partner_can_create_debt(partner_client, partner_user, store):
    url = reverse("store-debt-list")
    data = {
        "store": store.id,
        "amount": 5000,
        "description": "Test debt"
    }
    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_201_CREATED
    assert StoreDebt.objects.filter(created_by=partner_user).exists()


@pytest.mark.django_db
def test_admin_can_see_all_debts(admin_client, partner_user, store):
    StoreDebt.objects.create(store=store, amount=1000, created_by=partner_user)
    url = reverse("store-debt-list")
    response = admin_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1


@pytest.mark.django_db
def test_partner_can_see_only_own_debts(partner_client, admin_user, store):
    StoreDebt.objects.create(store=store, amount=1000, created_by=admin_user)
    url = reverse("store-debt-list")
    response = partner_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 0


@pytest.mark.django_db
def test_filter_by_store(partner_client, partner_user, store):
    debt1 = StoreDebt.objects.create(store=store, amount=500, created_by=partner_user)
    url = reverse("store-debt-list") + f"?store={store.id}"
    response = partner_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]['id'] == debt1.id


@pytest.mark.django_db
def test_mark_debt_as_paid(partner_client, partner_user, store):
    debt = StoreDebt.objects.create(store=store, amount=500, created_by=partner_user, is_paid=False)
    url = reverse("store-debt-mark-as-paid", args=[debt.id])
    response = partner_client.post(url, {"is_paid": True})
    assert response.status_code == status.HTTP_200_OK
    debt.refresh_from_db()
    assert debt.is_paid is True
    assert debt.paid_at is not None


@pytest.mark.django_db
def test_cannot_mark_already_paid_debt(partner_client, partner_user, store):
    debt = StoreDebt.objects.create(store=store, amount=500, created_by=partner_user, is_paid=True)
    url = reverse("store-debt-mark-as-paid", args=[debt.id])
    response = partner_client.post(url, {"is_paid": True})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_create_debt_with_negative_amount(partner_client, store):
    url = reverse("store-debt-list")
    data = {"store": store.id, "amount": -500, "description": "Invalid debt"}
    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_create_debt_without_amount(partner_client, store):
    url = reverse("store-debt-list")
    data = {"store": store.id, "description": "Missing amount"}
    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_cannot_mark_as_unpaid(partner_client, store, partner_user):
    debt = StoreDebt.objects.create(store=store, amount=1000, created_by=partner_user)
    url = reverse("store-debt-mark-as-paid", args=[debt.id])
    response = partner_client.post(url, {"is_paid": False})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "можно только отметить долг как оплаченный" in str(response.data).lower()


@pytest.mark.django_db
def test_cannot_mark_paid_twice(partner_client, store, partner_user):
    debt = StoreDebt.objects.create(store=store, amount=1000, created_by=partner_user, is_paid=True)
    url = reverse("store-debt-mark-as-paid", args=[debt.id])
    response = partner_client.post(url, {"is_paid": True})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "уже отмечен как оплаченный" in str(response.data).lower()


@pytest.mark.django_db
def test_partner_cannot_access_foreign_debt_detail(partner_client, admin_user, store):
    debt = StoreDebt.objects.create(store=store, amount=500, created_by=admin_user)
    url = reverse("store-debt-detail", args=[debt.id])
    response = partner_client.get(url)
    assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN]
