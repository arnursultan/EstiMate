import pytest
from django.urls import reverse
from rest_framework import status
from apps.stores.models import Store, City, StoreDebt

STORES_URL = reverse('store-list')
import pytest
from rest_framework.test import APIClient
from apps.users.models import User


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(
        email="admin@example.com",
        password="Admin1234",
        phone="+996700000001",
        first_name="Admin",
        last_name="User"
    )


@pytest.fixture
def auth_user():
    return User.objects.create_user(
        email="user@example.com",
        password="User1234",
        phone="+996700000002",
        first_name="Test",
        last_name="Partner",
        status="approved"
    )


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def auth_client(auth_user):
    client = APIClient()
    client.force_authenticate(user=auth_user)
    return client

@pytest.fixture
def city():
    return City.objects.create(name="Bishkek")

@pytest.mark.django_db
def test_create_store_by_partner(auth_client, city):
    data = {
        "name": "Test Store",
        "inn": "1234567890",
        "city": city.id,
        "address": "Some Street",
        "phone": "+996700000000"
    }
    response = auth_client.post(STORES_URL, data)
    assert response.status_code == status.HTTP_201_CREATED
    assert Store.objects.filter(name="Test Store").exists()

@pytest.mark.django_db
def test_admin_cannot_create_store(admin_client, city):
    data = {
        "name": "Admin Store",
        "inn": "1234567890",
        "city": city.id,
        "address": "Admin St",
        "phone": "+996700000001"
    }
    response = admin_client.post(STORES_URL, data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
def test_status_update_by_admin(admin_client, city):
    store = Store.objects.create(
        name="Pending Store", inn="1234567890", city=city,
        address="Address", phone="+996700000000", status="pending"
    )
    url = reverse("store-update-status", args=[store.id])
    response = admin_client.post(url, {"status": "approved"})
    assert response.status_code == status.HTTP_200_OK
    store.refresh_from_db()
    assert store.status == "approved"

@pytest.mark.django_db
def test_status_update_invalid_conditions(admin_client, city):
    store = Store.objects.create(
        name="AlreadyApproved", inn="1234567891", city=city,
        address="Addr", phone="+996700000001", status="approved"
    )
    url = reverse("store-update-status", args=[store.id])
    response = admin_client.post(url, {"status": "rejected"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST

@pytest.mark.django_db
def test_activate_deactivate_store(admin_client, city):
    store = Store.objects.create(
        name="Active Store", inn="9999999999", city=city,
        address="Some", phone="+996700000003", status="approved", is_active=False
    )

    activate_url = reverse("store-activate", args=[store.id])
    deactivate_url = reverse("store-deactivate", args=[store.id])

    response = admin_client.post(activate_url)
    assert response.status_code == status.HTTP_200_OK
    store.refresh_from_db()
    assert store.is_active is True

    response = admin_client.post(deactivate_url)
    assert response.status_code == status.HTTP_200_OK
    store.refresh_from_db()
    assert store.is_active is False

@pytest.mark.django_db
def test_cannot_activate_unapproved(admin_client, city):
    store = Store.objects.create(
        name="Pending", inn="1122334455", city=city,
        address="Nope", phone="+996700000004", status="pending", is_active=False
    )
    url = reverse("store-activate", args=[store.id])
    response = admin_client.post(url)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

@pytest.mark.django_db
def test_filter_only_approved_for_non_admin(auth_client, admin_client, city):
    Store.objects.create(name="Pending Store", inn="1111111111", city=city, address="A", phone="+996700000005", status="pending", is_active=True)
    Store.objects.create(name="Approved Store", inn="2222222222", city=city, address="B", phone="+996700000006", status="approved", is_active=True)
    Store.objects.create(name="Inactive Store", inn="3333333333", city=city, address="C", phone="+996700000007", status="approved", is_active=False)

    response = auth_client.get(STORES_URL)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["name"] == "Approved Store"

    response = admin_client.get(STORES_URL)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 3

@pytest.mark.django_db
def test_filter_by_city(auth_client, city):
    city2 = City.objects.create(name="Osh")
    Store.objects.create(name="Store1", inn="4444444444", city=city, address="X", phone="+996700000008", status="approved", is_active=True)
    Store.objects.create(name="Store2", inn="5555555555", city=city2, address="Y", phone="+996700000009", status="approved", is_active=True)

    url = f"{STORES_URL}?city={city.id}"
    response = auth_client.get(url)
    assert len(response.data) == 1
    assert response.data[0]["name"] == "Store1"

@pytest.mark.django_db
def test_filter_by_debt(admin_client, city):
    store1 = Store.objects.create(name="Debt1", inn="1231231230", city=city, address="Debt", phone="+996700000010", status="approved", is_active=True)
    store2 = Store.objects.create(name="Debt2", inn="1231231231", city=city, address="Debt", phone="+996700000011", status="approved", is_active=True)

    StoreDebt.objects.create(store=store1, amount=3000, is_paid=False)
    StoreDebt.objects.create(store=store2, amount=5000, is_paid=False)

    url = reverse("store-filter-by-debt")
    response = admin_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data[0]['name'] == "Debt2"  # highest debt first

@pytest.mark.django_db
def test_delete_not_allowed(admin_client, city):
    store = Store.objects.create(name="ToDelete", inn="1231231234", city=city, address="No", phone="+996700000012")
    url = reverse("store-detail", args=[store.id])
    response = admin_client.delete(url)
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert Store.objects.filter(id=store.id).exists()


@pytest.mark.django_db
def test_duplicate_inn_not_allowed(auth_client, city):
    Store.objects.create(name="One", inn="1231231230", city=city, address="A", phone="+996700000001")
    data = {
        "name": "Two",
        "inn": "1231231230",
        "city": city.id,
        "address": "B",
        "phone": "+996700000002"
    }
    response = auth_client.post(STORES_URL, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "inn" in response.data


@pytest.mark.django_db
def test_invalid_phone_format(auth_client, city):
    data = {
        "name": "InvalidPhoneStore",
        "inn": "1234567891",
        "city": city.id,
        "address": "Somewhere",
        "phone": "0070000000"  # без +
    }
    response = auth_client.post(STORES_URL, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "phone" in response.data


@pytest.mark.django_db
def test_activate_already_active_store(admin_client, city):
    store = Store.objects.create(name="AlreadyActive", inn="5555555555", city=city, address="Y", phone="+996700000099", status="approved", is_active=True)
    url = reverse("store-activate", args=[store.id])
    response = admin_client.post(url)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_deactivate_already_inactive_store(admin_client, city):
    store = Store.objects.create(name="AlreadyInactive", inn="5555555556", city=city, address="Y", phone="+996700000098", status="approved", is_active=False)
    url = reverse("store-deactivate", args=[store.id])
    response = admin_client.post(url)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
