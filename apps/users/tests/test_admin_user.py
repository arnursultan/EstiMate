from datetime import timedelta
from datetime import datetime, time
import pytest
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from apps.products.models import Product
from apps.orders.models import ProductRequest
from apps.stores.models import StoreDebt, City, Store
from apps.finance.models import FinanceEntry
from django.utils import timezone

User = get_user_model()

@pytest.fixture
def admin_user():
    return User.objects.create_superuser(
        email="admin@gmail.com",
        password="Admin1234",
        phone="+996700000001",
        first_name="Админ",
        last_name="Тестов"
    )

@pytest.fixture
def regular_user():
    return User.objects.create_user(
        email="user@gmail.com",
        password="User1234",
        phone="+996700000002",
        first_name="Айбек",
        last_name="Тестов",
        status="approved"
    )

@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.mark.django_db
def test_admin_get_user_list_all(admin_client, regular_user):
    url = reverse("admin")
    response = admin_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.data, list)
    assert any(u["email"] == regular_user.email for u in response.data)


@pytest.mark.django_db
def test_admin_get_user_list_filtered_by_email(admin_client, regular_user):
    url = reverse("admin")
    response = admin_client.get(url, {"email": "user@"})

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) >= 1
    assert all("user@" in u["email"] for u in response.data)


@pytest.mark.django_db
def test_non_admin_cannot_access_user_list(regular_user):
    client = APIClient()
    client.force_authenticate(user=regular_user)

    url = reverse("admin")
    response = client.get(url)

    assert response.status_code == status.HTTP_403_FORBIDDEN


# ✅ Успешный запрос админа
@pytest.mark.django_db
def test_admin_get_user_detail(admin_client, regular_user):
    url = reverse("admin_detail", kwargs={"pk": regular_user.pk})
    response = admin_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["email"] == regular_user.email
    assert response.data["id"] == regular_user.id

# ❌ Несуществующий пользователь
@pytest.mark.django_db
def test_admin_get_nonexistent_user(admin_client):
    url = reverse("admin_detail", kwargs={"pk": 99999})
    response = admin_client.get(url)

    assert response.status_code == status.HTTP_404_NOT_FOUND

# ❌ Не-админ не может получить данные другого пользователя
@pytest.mark.django_db
def test_non_admin_cannot_get_user_detail(regular_user):
    client = APIClient()
    client.force_authenticate(user=regular_user)
    url = reverse("admin_detail", kwargs={"pk": regular_user.pk})
    response = client.get(url)

    assert response.status_code == status.HTTP_403_FORBIDDEN

# ✅ Успешное обновление пользователя админом (PATCH)
@pytest.mark.django_db
def test_admin_patch_user(admin_client, regular_user):
    url = reverse("admin_detail", kwargs={"pk": regular_user.pk})
    data = {"first_name": "Обновлённый"}

    response = admin_client.patch(url, data)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["first_name"] == "Обновлённый"


# ✅ Успешное обновление пользователя админом (PUT)
@pytest.mark.django_db
def test_admin_put_user(admin_client, regular_user):
    url = reverse("admin_detail", kwargs={"pk": regular_user.pk})
    data = {
        "email": "updated@gmail.com",
        "phone": "+996700000099",
        "first_name": "НовоеИмя",
        "last_name": "Фамилия",
        "password": "NewPass1234"
    }

    response = admin_client.put(url, data)
    print(response.data)
    assert response.status_code == status.HTTP_200_OK
    print(response.data)
    assert response.data["email"] == "updated@gmail.com"

    regular_user.refresh_from_db()
    assert regular_user.check_password("NewPass1234")


# Email ❌
@pytest.mark.django_db
def test_admin_patch_user_duplicate_email(admin_client, regular_user):
    other = User.objects.create_user(
        email="dupe@gmail.com",
        password="Test1234",
        phone="+996700000077",
        first_name="Other",
        last_name="User"
    )

    url = reverse("admin_detail", kwargs={"pk": regular_user.pk})
    data = {"email": "dupe@gmail.com"}

    response = admin_client.patch(url, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.data


# ❌ PUT без обязательного поля (например, без email)
@pytest.mark.django_db
def test_admin_put_user_missing_required(admin_client, regular_user):
    url = reverse("admin_detail", kwargs={"pk": regular_user.pk})
    data = {
        # "email" отсутствует
        "phone": "+996700000099",
        "first_name": "НовоеИмя",
        "last_name": "Фамилия",
        "password": "NewPass1234"
    }

    response = admin_client.put(url, data, format="multipart")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.data


@pytest.mark.django_db
def test_admin_delete_user(admin_client, regular_user):
    url = reverse("delete", kwargs={"pk": regular_user.pk})
    response = admin_client.delete(url)

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not User.objects.filter(pk=regular_user.pk).exists()

# ❌ Удаление несуществующего пользователя
@pytest.mark.django_db
def test_admin_delete_nonexistent_user(admin_client):
    url = reverse("delete", kwargs={"pk": 99999})
    response = admin_client.delete(url)

    assert response.status_code == status.HTTP_404_NOT_FOUND

# ❌ Не-админ не может удалить пользователя
@pytest.mark.django_db
def test_non_admin_cannot_delete_user(regular_user):
    client = APIClient()
    client.force_authenticate(user=regular_user)

    url = reverse("delete", kwargs={"pk": regular_user.pk})
    response = client.delete(url)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert User.objects.filter(pk=regular_user.pk).exists()




# ✅ Успешная блокировка
@pytest.mark.django_db
def test_admin_block_user(admin_client, regular_user):
    url = reverse("block", kwargs={"pk": regular_user.pk})
    response = admin_client.post(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["detail"] == "Пользователь успешно заблокирован"

    regular_user.refresh_from_db()
    assert not regular_user.is_active

# ❌ Уже заблокированный пользователь
@pytest.mark.django_db
def test_admin_block_already_blocked_user(admin_client, regular_user):
    regular_user.is_active = False
    regular_user.save()

    url = reverse("block", kwargs={"pk": regular_user.pk})
    response = admin_client.post(url)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "уже заблокирован" in response.data["detail"]

# ❌ Несуществующий пользователь
@pytest.mark.django_db
def test_admin_block_nonexistent_user(admin_client):
    url = reverse("block", kwargs={"pk": 99999})
    response = admin_client.post(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ✅ Успешная разблокировка
@pytest.mark.django_db
def test_admin_unblock_user(admin_client, regular_user):
    regular_user.is_active = False
    regular_user.save()

    url = reverse("unblock", kwargs={"pk": regular_user.pk})
    response = admin_client.post(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["detail"] == "Пользователь успешно разблокирован"

    regular_user.refresh_from_db()
    assert regular_user.is_active

# ❌ Уже активный пользователь
@pytest.mark.django_db
def test_admin_unblock_active_user(admin_client, regular_user):
    url = reverse("unblock", kwargs={"pk": regular_user.pk})
    response = admin_client.post(url)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "уже активен" in response.data["detail"]

# ❌ Несуществующий пользователь
@pytest.mark.django_db
def test_admin_unblock_nonexistent_user(admin_client):
    url = reverse("unblock", kwargs={"pk": 99999})
    response = admin_client.post(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND



# ✅ Успешное одобрение пользователя
@pytest.mark.django_db
def test_approve_user_success(admin_client, regular_user):
    regular_user.status = "pending"
    regular_user.save()
    url = reverse("approve", kwargs={"pk": regular_user.pk})
    response = admin_client.post(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "approved"


# ❌ Пользователь уже одобрен
@pytest.mark.django_db
def test_approve_user_already_approved(admin_client, regular_user):
    regular_user.status = "approved"
    regular_user.save()

    url = reverse("approve", kwargs={"pk": regular_user.pk})
    response = admin_client.post(url)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "уже одобрен" in response.data["detail"]


# ✅ Успешное отклонение пользователя
@pytest.mark.django_db
def test_reject_user_success(admin_client, regular_user):
    url = reverse("reject", kwargs={"pk": regular_user.pk})
    response = admin_client.post(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "rejected"


# ❌ Пользователь уже отклонён
@pytest.mark.django_db
def test_reject_user_already_rejected(admin_client, regular_user):
    regular_user.status = "rejected"
    regular_user.save()

    url = reverse("reject", kwargs={"pk": regular_user.pk})
    response = admin_client.post(url)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "уже отклонён" in response.data["detail"]


# ❌ Не-админ не может одобрить пользователя
@pytest.mark.django_db
def test_non_admin_cannot_approve_user(regular_user):
    client = APIClient()
    client.force_authenticate(user=regular_user)

    url = reverse("approve", kwargs={"pk": regular_user.pk})
    response = client.post(url)

    assert response.status_code == status.HTTP_403_FORBIDDEN


# ❌ Не-админ не может отклонить пользователя
@pytest.mark.django_db
def test_non_admin_cannot_reject_user(regular_user):
    client = APIClient()
    client.force_authenticate(user=regular_user)

    url = reverse("reject", kwargs={"pk": regular_user.pk})
    response = client.post(url)

    assert response.status_code == status.HTTP_403_FORBIDDEN


# ❌ Попытка одобрить несуществующего пользователя
@pytest.mark.django_db
def test_approve_nonexistent_user(admin_client):
    url = reverse("approve", kwargs={"pk": 99999})
    response = admin_client.post(url)

    assert response.status_code == status.HTTP_404_NOT_FOUND


# ❌ Попытка отклонить несуществующего пользователя
@pytest.mark.django_db
def test_reject_nonexistent_user(admin_client):
    url = reverse("reject", kwargs={"pk": 99999})
    response = admin_client.post(url)

    assert response.status_code == status.HTTP_404_NOT_FOUND



@pytest.mark.django_db
class TestAdminDashboardView:

    @pytest.fixture
    def url(self):
        return reverse("admin-dashboard")

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def admin(self):
        return User.objects.create_user(
            email="admin@example.com",
            password="adminpass",
            is_staff=True,
            phone="7770000001",
            first_name="Admin",
            last_name="Test",
            is_active=True,
            status="approved",
        )

    @pytest.fixture
    def user(self):
        return User.objects.create_user(
            email="user@example.com",
            password="userpass",
            is_staff=False,
            phone="7770000002",
            first_name="User",
            last_name="Test",
            is_active=True,
            status="pending"
        )

    def test_admin_success(self, client, admin, url):
        client.force_authenticate(user=admin)
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert set(response.data.keys()) == {
            "date",
            "user_stats",
            "product_stats",
            "order_stats",
            "debt_stats",
            "finance_stats",
            "recent_activities"
        }

    def test_forbidden_for_non_admin(self, client, user, url):
        client.force_authenticate(user=user)
        response = client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthorized_if_not_logged_in(self, client, url):
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_full_data_aggregation(self, client, admin, url):
        today = timezone.localtime().date()

        # Город
        city = City.objects.create(name="TestCity")

        # Пользователи
        User.objects.create_user(
            email="1@t.com", password="x", is_active=True,
            status="approved",
            phone="7770000003", first_name="User1", last_name="Test"
        )
        User.objects.create_user(
            email="2@t.com", password="x", is_active=False,
            status="pending", phone="7770000004", first_name="User2", last_name="Test"
        )

        # Товары
        p1 = Product.objects.create(name="Product1", quantity=0, price=100)
        p2 = Product.objects.create(name="Product2", quantity=5, price=50)
        p3 = Product.objects.create(name="Product3", quantity=20, price=130)

        # Заказы
        ProductRequest.objects.create(
            user=admin,
            product=p1,
            status="pending",
            quantity=1,
            created_at=timezone.now()
        )
        ProductRequest.objects.create(
            user=admin,
            product=p2,
            status="approved",
            quantity=1,
            created_at=timezone.now()
        )
        ProductRequest.objects.create(
            user=admin,
            product=p3,
            status="received",
            payment_method="cash",
            total_price=120,
            quantity=1,
            created_at=timezone.now()
        )

        # Магазин
        store = Store.objects.create(
            name="Test Store",
            inn="12345678901234",
            city=city,
            address="ул. Центральная, 1",
            phone="0700123456",
            status="approved",
            is_active=True,
            creator=admin
        )

        # Долги
        StoreDebt.objects.create(store=store, amount=200, is_paid=False)
        StoreDebt.objects.create(store=store, amount=100, is_paid=True, paid_at=timezone.now())

        # Финансы
        FinanceEntry.objects.create(user=admin, date=today, amount=50, entry_type="expense")

        # Запрос
        client.force_authenticate(user=admin)
        response = client.get(url)
        data = response.data

        assert data["user_stats"]["total_users"] == 2
        assert data["user_stats"]["active_users"] == 1
        assert data["user_stats"]["pending_approvals"] == 1

        assert data["product_stats"]["total_products"] == 3
        assert data["product_stats"]["out_of_stock"] == 1
        assert data["product_stats"]["low_stock"] == 1

        assert data["order_stats"]["new_requests"] == 1
        assert data["order_stats"]["approved_requests"] == 1
        assert data["order_stats"]["completed_requests"] == 1

        assert data["debt_stats"]["total_debt"] == 200.0
        assert data["debt_stats"]["debts_count"] == 1
        assert data["debt_stats"]["debts_paid_today"] == 1

        assert data["finance_stats"]["today_income"] == 130.0
        assert data["finance_stats"]["today_expenses"] == 50.0

    def test_no_data_still_works(self, client, admin, url):
        client.force_authenticate(user=admin)
        response = client.get(url)
        data = response.data

        assert response.status_code == status.HTTP_200_OK
        assert data["user_stats"]["total_users"] == 0
        assert data["product_stats"]["total_products"] == 0
        assert data["order_stats"]["new_requests"] == 0
        assert data["debt_stats"]["total_debt"] == 0.0
        assert data["finance_stats"]["today_expenses"] == 0.0





@pytest.mark.django_db
class TestPartnerDailySummaryView:

    @pytest.fixture
    def url(self):
        return reverse("daily-summary")

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def partner(self):
        return User.objects.create_user(
            email="partner@example.com",
            password="partnerpass",
            is_staff=False,
            phone="7770000007",
            first_name="Partner",
            last_name="Test",
            status="approved",
            is_active=True
        )

    @pytest.fixture
    def setup_data(self, partner):
        today = timezone.localtime().date()

        p1 = Product.objects.create(name="Product 1", quantity=100, price=100, is_bonus_eligible=True)
        p2 = Product.objects.create(name="Product 2", quantity=100, price=80, is_bonus_eligible=False)
        p3 = Product.objects.create(name="Product 3", quantity=100, price=60, is_bonus_eligible=True)

        ProductRequest.objects.create(
            user=partner, product=p1, quantity=21, status='pending',
            request_type='SELF', created_at=datetime.combine(today, time.min).replace(tzinfo=timezone.get_current_timezone())
        )
        ProductRequest.objects.create(
            user=partner, product=p2, quantity=3, status='approved',
            request_type='SELF', created_at=datetime.combine(today, time.min).replace(tzinfo=timezone.get_current_timezone())
        )
        ProductRequest.objects.create(
            user=partner, product=p3, quantity=42, status='received',
            request_type='SELF', created_at=datetime.combine(today, time.min).replace(tzinfo=timezone.get_current_timezone())
        )

        FinanceEntry.objects.create(
            user=partner, date=today, amount=75, entry_type="expense"
        )

        return {"date": today, "products": [p1, p2, p3]}

    def test_authenticated_summary(self, client, partner, url, setup_data):
        client.force_authenticate(user=partner)
        response = client.get(url, {"date": setup_data["date"].isoformat()})
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        summary = data["summary"]
        assert summary["total_requested"] == 66  # 21 + 3 + 42
        assert summary["total_sold"] == 42       # только received
        assert summary["total_remaining"] == 24  # pending + approved
        assert summary["total_bonus"] == 3       # 1 (21//21) + 0 + 2 (42//21)
        assert summary["total_expenses"] == 75.0

    def test_unauthenticated(self, client, url):
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_date_format(self, client, partner, url):
        client.force_authenticate(user=partner)
        response = client.get(url, {"date": "2024-99-99"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data

    def test_no_data_returns_zeros(self, client, partner, url):
        client.force_authenticate(user=partner)
        future_date = (timezone.localtime().date() + timedelta(days=30)).isoformat()
        response = client.get(url, {"date": future_date})
        summary = response.data["summary"]
        assert summary["total_requested"] == 0
        assert summary["total_sold"] == 0
        assert summary["total_remaining"] == 0
        assert summary["total_bonus"] == 0
        assert summary["total_expenses"] == 0.0

    def test_all_non_bonus_products(self, client, partner, url):
        today = timezone.localtime().date()

        p1 = Product.objects.create(name="NoBonus1", quantity=100, price=100, is_bonus_eligible=False)
        p2 = Product.objects.create(name="NoBonus2", quantity=100, price=200, is_bonus_eligible=False)

        ProductRequest.objects.create(user=partner, product=p1, quantity=5, request_type="SELF", status="pending")
        ProductRequest.objects.create(user=partner, product=p2, quantity=10, request_type="SELF", status="received")

        client.force_authenticate(user=partner)
        response = client.get(url, {"date": today.isoformat()})
        assert response.data["summary"]["total_bonus"] == 0

    def test_all_rejected_requests(self, client, partner, url):
        today = timezone.localtime().date()
        product = Product.objects.create(name="RejectedProd", quantity=50, price=70)

        ProductRequest.objects.create(user=partner, product=product, quantity=4, request_type="SELF", status="rejected")

        client.force_authenticate(user=partner)
        response = client.get(url, {"date": today.isoformat()})

        summary = response.data["summary"]
        assert summary["total_requested"] == 4
        assert summary["total_sold"] == 0
        assert summary["total_remaining"] == 0


    def test_bonus_when_quantity_zero(self, client, partner, url):
        today = timezone.localtime().date()
        product = Product.objects.create(name="ZeroQtyBonus", quantity=0, price=50, is_bonus_eligible=True)

        ProductRequest.objects.create(user=partner, product=product, quantity=42, request_type="SELF", status="approved")

        client.force_authenticate(user=partner)
        response = client.get(url, {"date": today.isoformat()})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["summary"]["total_bonus"] >= 2
