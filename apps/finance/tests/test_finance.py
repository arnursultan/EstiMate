import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta
from apps.finance.models import PartnerFinanceStat
from apps.users.models import User

# === FIXTURES ===

@pytest.fixture
def partner_user():
    return User.objects.create_user(
        email="partner@example.com",  # ← добавили
        phone="77770000001",
        first_name="Партнёр",
        last_name="Тестович",
        password="password123"
    )

@pytest.fixture
def another_partner():
    return User.objects.create_user(
        email="another@example.com",  # ← добавили
        phone="77770000002",
        first_name="Другой",
        last_name="Партнёр",
        password="password123"
    )

@pytest.fixture
def auth_client(partner_user):
    client = APIClient()
    client.force_authenticate(user=partner_user)
    return client

@pytest.fixture
def partner_stats(partner_user):
    today = timezone.now().date()
    return PartnerFinanceStat.objects.bulk_create([
        PartnerFinanceStat(
            user=partner_user,
            date=today - timedelta(days=2),
            total_requested_amount=1000,
            total_sold_amount=1500,
            total_expenses=200
        ),
        PartnerFinanceStat(
            user=partner_user,
            date=today - timedelta(days=1),
            total_requested_amount=500,
            total_sold_amount=700,
            total_expenses=100
        ),
        PartnerFinanceStat(
            user=partner_user,
            date=today,
            total_requested_amount=800,
            total_sold_amount=900,
            total_expenses=150
        ),
    ])

@pytest.fixture
def another_user_stats(another_partner):
    today = timezone.now().date()
    return PartnerFinanceStat.objects.bulk_create([
        PartnerFinanceStat(
            user=another_partner,
            date=today,
            total_requested_amount=999,
            total_sold_amount=999,
            total_expenses=999
        )
    ])


# === TESTS ===

@pytest.mark.django_db
def test_get_finance_stats_success(auth_client, partner_stats, another_user_stats):
    url = reverse("finance:my-finance")
    response = auth_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 3
    assert all("total_requested_amount" in stat for stat in data)
    # Проверяем сортировку по убыванию даты
    dates = [stat["date"] for stat in data]
    assert dates == sorted(dates, reverse=True)

@pytest.mark.django_db
def test_get_finance_stats_unauthorized():
    client = APIClient()
    url = reverse("finance:my-finance")
    response = client.get(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.django_db
def test_no_stats_returned_for_other_user(auth_client, another_user_stats):
    url = reverse("finance:my-finance")
    response = auth_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data == []  # Статистики у пользователя нет
