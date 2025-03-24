import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

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

