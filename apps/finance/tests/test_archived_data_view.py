import pytest
from datetime import date
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.finance.models import ArchivedDailySummary
from apps.users.models import User


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(
        email="admin@example.com",
        phone="700000000",
        password="adminpass",
        first_name="Admin",
        last_name="Adminov"
    )


@pytest.fixture
def partner_user():
    return User.objects.create_user(
        email="partner@example.com",
        phone="700000001",
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
def archived_entry(partner_user):
    return ArchivedDailySummary.objects.create(
        user=partner_user,
        date=date.today(),
        total_requests=5,
        total_sales=1000,
        total_expenses=300,
        total_profit=700,
        data={"example": "value"}
    )


@pytest.mark.django_db
def test_partner_sees_own_archive(partner_client, archived_entry):
    url = reverse("finance:archived-data")
    response = partner_client.get(url, {"date": date.today().isoformat()})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["user"]["email"] == archived_entry.user.email
    assert data[0]["total_profit"] == float(archived_entry.total_profit)


@pytest.mark.django_db
def test_admin_sees_all_archives(admin_client, archived_entry):
    url = reverse("finance:archived-data")
    response = admin_client.get(url, {"date": date.today().isoformat()})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) >= 1
    assert any(d["user"]["email"] == archived_entry.user.email for d in data)


@pytest.mark.django_db
def test_missing_date_param_returns_400(partner_client):
    url = reverse("finance:archived-data")
    response = partner_client.get(url)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "error" in response.json()


@pytest.mark.django_db
def test_invalid_date_format_returns_400(partner_client):
    url = reverse("finance:archived-data")
    response = partner_client.get(url, {"date": "not-a-date"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "error" in response.json()


@pytest.mark.django_db
def test_no_data_returns_404(partner_client):
    url = reverse("finance:archived-data")
    response = partner_client.get(url, {"date": "2020-01-01"})
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "message" in response.json()


@pytest.mark.django_db
def test_unauthenticated_cannot_access():
    client = APIClient()
    url = reverse("finance:archived-data")
    response = client.get(url, {"date": date.today().isoformat()})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_admin_sees_archives_for_all_users(admin_client, partner_user, admin_user):
    from apps.finance.models import ArchivedDailySummary
    from datetime import date

    date_today = date.today()

    ArchivedDailySummary.objects.create(
        user=partner_user,
        date=date_today,
        total_requests=5,
        total_sales=100,
        total_expenses=10,
        total_profit=90,
        data={"partner": "yes"}
    )
    ArchivedDailySummary.objects.create(
        user=admin_user,
        date=date_today,
        total_requests=3,
        total_sales=300,
        total_expenses=20,
        total_profit=280,
        data={"admin": "yes"}
    )

    url = reverse("finance:archived-data")
    response = admin_client.get(url, {"date": date_today.isoformat()})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    emails = [entry["user"]["email"] for entry in data]
    assert partner_user.email in emails
    assert admin_user.email in emails
    assert len(data) == 2


@pytest.mark.django_db
def test_details_field_is_returned_correctly(admin_client, partner_user):
    from apps.finance.models import ArchivedDailySummary
    from datetime import date

    details_data = {"products": [{"name": "Товар", "sold": 5}]}
    date_today = date.today()

    ArchivedDailySummary.objects.create(
        user=partner_user,
        date=date_today,
        total_requests=2,
        total_sales=50,
        total_expenses=5,
        total_profit=45,
        data=details_data
    )

    url = reverse("finance:archived-data")
    response = admin_client.get(url, {"date": date_today.isoformat()})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data[0]["details"] == details_data



@pytest.mark.django_db
def test_partner_does_not_see_others_archives(partner_client, partner_user, admin_user):
    from apps.finance.models import ArchivedDailySummary
    from datetime import date

    date_today = date.today()

    # Архив партнёра
    ArchivedDailySummary.objects.create(
        user=partner_user,
        date=date_today,
        total_requests=1,
        total_sales=10,
        total_expenses=2,
        total_profit=8,
        data={"own": "data"}
    )

    # Архив админа (должен быть недоступен партнёру)
    ArchivedDailySummary.objects.create(
        user=admin_user,
        date=date_today,
        total_requests=5,
        total_sales=200,
        total_expenses=50,
        total_profit=150,
        data={"admin": "hidden"}
    )

    url = reverse("finance:archived-data")
    response = partner_client.get(url, {"date": date_today.isoformat()})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["user"]["email"] == partner_user.email
    assert "admin" not in data[0]["details"]
