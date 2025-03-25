import pytest
from rest_framework import status
from rest_framework.test import APIClient
from django.urls import reverse
from datetime import date
from apps.finance.models import PartnerFinanceStat, StoreFinanceStat, FinanceEntry
from apps.stores.models import City, Store
from django.contrib.auth import get_user_model

User = get_user_model()

# ====== USERS ======

@pytest.fixture
def partner():
    return User.objects.create_user(
        email="partner1@example.com",
        password="testpass123",
        role="partner",
        phone="+79999999999",
        first_name="Партнёр",
        last_name="Один"
    )

@pytest.fixture
def admin():
    return User.objects.create_user(
        email="admin@example.com",
        password="adminpass123",
        role="admin",
        phone="+70000000000",
        first_name="Админ",
        last_name="Системы",
        is_staff=True
    )

@pytest.fixture
def api_client_partner(partner):
    client = APIClient()
    client.force_authenticate(user=partner)
    return client

@pytest.fixture
def api_client_admin(admin):
    client = APIClient()
    client.force_authenticate(user=admin)
    return client

@pytest.fixture
def other_partner():
    return User.objects.create_user(
        email="partner2@example.com",
        password="testpass123",
        role="partner",
        phone="+78888888888",
        first_name="Партнёр",
        last_name="Два"
    )

@pytest.fixture
def api_client_other_partner(other_partner):
    client = APIClient()
    client.force_authenticate(user=other_partner)
    return client

# ====== URLS ======

@pytest.fixture
def urls():
    return {
        'my': reverse('finance:my-finance'),
        'stores': reverse('finance:store-finance'),
        'manual': reverse('finance:manual-finance'),
    }

# ====== DATA FIXTURES ======

@pytest.fixture
def city():
    return City.objects.create(name="Москва")

@pytest.fixture
def partner_stats(partner):
    return PartnerFinanceStat.objects.create(
        user=partner,
        date=date.today(),
        total_approved_cash=1000,
        total_damaged_loss=200,
        total_profit=800
    )

@pytest.fixture
def store_and_stat(city):
    store = Store.objects.create(
        name="Test Store",
        city=city,
        inn="1234567890",
        address="г. Москва",
        phone="+79991112233"
    )
    return StoreFinanceStat.objects.create(
        store=store,
        date=date.today(),
        total_approved=5000,
        total_damaged=300,
        total_debt=1000
    )

@pytest.fixture
def finance_entry(partner, city):
    return FinanceEntry.objects.create(
        user=partner,
        date=date.today(),
        income=1000,
        expense=400,
        profit=600,
        city=city,
        note="Тестовый ввод"
    )

@pytest.fixture
def other_finance_entry(other_partner, city):
    return FinanceEntry.objects.create(
        user=other_partner,
        date=date.today(),
        income=123,
        expense=23,
        profit=100,
        city=city,
        note="Чужая запись"
    )

@pytest.fixture
def multiple_entries(partner, city):
    FinanceEntry.objects.create(
        user=partner, city=city, date=date(2024, 5, 1),
        income=100, expense=20, profit=80, note="Старый"
    )
    FinanceEntry.objects.create(
        user=partner, city=city, date=date(2025, 1, 1),
        income=200, expense=30, profit=170, note="Новый"
    )

# ====== TESTS ======

@pytest.mark.django_db
class TestMyFinanceStatView:

    def test_requires_auth(self, client, urls):
        response = client.get(urls['my'])
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_returns_own_stats(self, api_client_partner, urls, partner_stats):
        response = api_client_partner.get(urls['my'])
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert float(response.data[0]['total_profit']) == 800.0

    def test_does_not_see_other_users(self, api_client_other_partner, urls, partner_stats):
        response = api_client_other_partner.get(urls['my'])
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

@pytest.mark.django_db
class TestStoreFinanceView:

    def test_admin_can_access(self, api_client_admin, urls, store_and_stat):
        response = api_client_admin.get(urls['stores'])
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert float(response.data[0]['total_debt']) == 1000.0

    def test_partner_cannot_access(self, api_client_partner, urls):
        response = api_client_partner.get(urls['stores'])
        assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
class TestManualFinanceEntryView:

    def test_list_own_entries(self, api_client_partner, urls, finance_entry):
        response = api_client_partner.get(urls['manual'])
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert float(response.data[0]['profit']) == 600.0

    def test_filter_by_city_and_date(self, api_client_partner, urls, finance_entry, city):
        date_str = finance_entry.date.isoformat()
        response = api_client_partner.get(f"{urls['manual']}?city={city.id}&date={date_str}")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_create_entry(self, api_client_partner, urls, city):
        payload = {
            "date": date.today(),
            "income": 1500,
            "expense": 500,
            "profit": 1000,
            "city": city.id,
            "note": "Создано вручную"
        }
        response = api_client_partner.post(urls['manual'], payload, format='json')
        assert response.status_code == 201
        assert float(response.data['income']) == 1500.0
        assert response.data['user']

    def test_unauthenticated_cannot_create(self, client, urls, city):
        payload = {
            "date": date.today(),
            "income": 1500,
            "expense": 500,
            "profit": 1000,
            "city": city.id,
            "note": "Аноним"
        }
        response = client.post(urls['manual'], payload, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.django_db
class TestManualFinanceEntryEdgeCases:

    def test_user_field_ignored_on_create(self, api_client_partner, urls, city, admin):
        payload = {
            "date": date.today(),
            "income": 999,
            "expense": 100,
            "profit": 899,
            "city": city.id,
            "note": "Попытка чужого user",
            "user": admin.id
        }
        response = api_client_partner.post(urls['manual'], payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['user'] != admin.id

    def test_create_entry_negative_income(self, api_client_partner, urls, city):
        payload = {
            "date": date.today(),
            "income": -100,
            "expense": 500,
            "profit": -600,
            "city": city.id,
            "note": "Отрицательные значения"
        }
        response = api_client_partner.post(urls['manual'], payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_filter_with_nonexistent_date(self, api_client_partner, urls, city):
        response = api_client_partner.get(f"{urls['manual']}?city={city.id}&date=2099-01-01")
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_does_not_see_others_entries(self, api_client_partner, urls, other_finance_entry):
        response = api_client_partner.get(urls['manual'])
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_create_missing_required_fields(self, api_client_partner, urls):
        response = api_client_partner.post(urls['manual'], {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'date' in response.data

    def test_entries_sorted_by_date_desc(self, api_client_partner, urls, multiple_entries):
        response = api_client_partner.get(urls['manual'])
        assert response.status_code == status.HTTP_200_OK
        dates = [entry['date'] for entry in response.data]
        assert dates == sorted(dates, reverse=True)