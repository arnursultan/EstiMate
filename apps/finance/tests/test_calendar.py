import pytest
from datetime import date
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.finance.models import CalendarStatistics
from apps.users.models import User
from apps.stores.models import Store, City


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
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def partner_client(partner_user):
    client = APIClient()
    client.force_authenticate(user=partner_user)
    return client


@pytest.fixture
def city():
    return City.objects.create(name="ТестГород")


@pytest.fixture
def store(city):
    return Store.objects.create(
        name="Тестовый магазин",
        inn="123456789012",
        city=city,
        address="Тест адрес",
        phone="+99670000007",
        status="approved",
        is_active=True,
    )

@pytest.fixture
def calendar_entry(partner_user, store, city):
    return CalendarStatistics.objects.create(
        user=partner_user,
        store=store,
        city=city,
        date=date.today(),
        has_sales=True,
        has_requests=False,
        has_expenses=False,
        has_debt_payment=False
    )

@pytest.fixture
def calendar_stat(partner_user, store, city):
    return CalendarStatistics.objects.create(
        user=partner_user,
        store=store,
        city=city,
        date=date.today(),
        has_sales=True,
        has_requests=False,
        has_expenses=True,
        has_debt_payment=False
    )


@pytest.mark.django_db
def test_partner_sees_only_own_calendar(partner_client, calendar_stat):
    url = reverse("finance:calendar-statistics")
    response = partner_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    dates = response.json()["dates"]
    assert date.today().isoformat() in dates
    assert dates[date.today().isoformat()]["has_sales"] is True
    assert dates[date.today().isoformat()]["has_expenses"] is True


@pytest.mark.django_db
def test_admin_sees_all_calendar(admin_client, calendar_stat):
    url = reverse("finance:calendar-statistics")
    response = admin_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    dates = response.json()["dates"]
    assert date.today().isoformat() in dates


@pytest.mark.django_db
def test_filter_by_year_and_month(partner_client, calendar_stat):
    today = date.today()
    url = reverse("finance:calendar-statistics")
    response = partner_client.get(url, {"year": today.year, "month": today.month})
    assert response.status_code == status.HTTP_200_OK
    assert date.today().isoformat() in response.json()["dates"]


@pytest.mark.django_db
def test_filter_by_store_and_city(partner_client, calendar_stat, store, city):
    url = reverse("finance:calendar-statistics")
    response = partner_client.get(url, {"store": store.id, "city": city.id})
    assert response.status_code == status.HTTP_200_OK
    assert date.today().isoformat() in response.json()["dates"]


@pytest.mark.django_db
def test_unauthorized_user_cannot_access():
    client = APIClient()
    url = reverse("finance:calendar-statistics")
    response = client.get(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_calendar_no_data_returns_empty(admin_client):
    url = reverse("finance:calendar-statistics")
    response = admin_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"dates": {}}


@pytest.mark.django_db
def test_calendar_nonexistent_city_returns_empty(admin_client):
    url = reverse("finance:calendar-statistics")
    response = admin_client.get(url, {"city": 9999})
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"dates": {}}


@pytest.mark.django_db
def test_calendar_invalid_year_returns_empty(admin_client):
    url = reverse("finance:calendar-statistics")
    response = admin_client.get(url, {"year": 1999})
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"dates": {}}


@pytest.mark.django_db
def test_calendar_store_and_city_mismatch_returns_empty(admin_client, calendar_entry):
    from apps.stores.models import City
    another_city = City.objects.create(name="Несовпадающий город")
    url = reverse("finance:calendar-statistics")
    response = admin_client.get(url, {
        "store": calendar_entry.store.id,
        "city": another_city.id
    })

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"dates": {}}



@pytest.mark.django_db
def test_calendar_unauthenticated_user():
    client = APIClient()
    url = reverse("finance:calendar-statistics")
    response = client.get(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED