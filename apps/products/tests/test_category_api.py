import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.products.models import Category
from apps.users.models import User

CATEGORIES_URL = reverse("category-list")

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
def normal_user():
    return User.objects.create_user(
        email="user@example.com",
        password="User1234",
        phone="+996700000002",
        first_name="User",
        last_name="Test",
        status="approved"
    )

@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client

@pytest.fixture
def user_client(normal_user):
    client = APIClient()
    client.force_authenticate(user=normal_user)
    return client

@pytest.fixture
def category():
    return Category.objects.create(name="Beverages")

@pytest.mark.django_db
def test_list_categories(user_client, category):
    response = user_client.get(CATEGORIES_URL)
    assert response.status_code == status.HTTP_200_OK
    assert any(c["name"] == "Beverages" for c in response.data)

@pytest.mark.django_db
def test_create_category_admin_only(admin_client, user_client):
    data = {"name": "Snacks"}

    # ✅ Админ может создать
    response = admin_client.post(CATEGORIES_URL, data)
    assert response.status_code == status.HTTP_201_CREATED
    assert Category.objects.filter(name="Snacks").exists()

    # ❌ Обычный пользователь — нет
    response = user_client.post(CATEGORIES_URL, data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
def test_create_invalid_category(admin_client):
    response = admin_client.post(CATEGORIES_URL, {"name": ""})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "name" in response.data

@pytest.mark.django_db
def test_search_category(user_client):
    Category.objects.create(name="Milk")
    Category.objects.create(name="Water")
    Category.objects.create(name="Chocolate")

    response = user_client.get(f"{CATEGORIES_URL}?search=cho")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["name"] == "Chocolate"

@pytest.mark.django_db
def test_ordering_category(user_client):
    Category.objects.create(name="Water")
    Category.objects.create(name="Bread")
    Category.objects.create(name="Apple")

    response = user_client.get(f"{CATEGORIES_URL}?ordering=name")
    names = [cat["name"] for cat in response.data]
    assert names == sorted(names)



@pytest.mark.django_db
def test_create_category_empty_name(admin_client):
    response = admin_client.post(CATEGORIES_URL, {"name": ""})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "name" in response.data


@pytest.mark.django_db
def test_create_duplicate_category(admin_client):
    Category.objects.create(name="Dairy")
    response = admin_client.post(CATEGORIES_URL, {"name": "Dairy"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_non_admin_cannot_update_category(user_client):
    category = Category.objects.create(name="Fruit")
    url = reverse("category-detail", args=[category.id])
    response = user_client.patch(url, {"name": "Updated"})
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_admin_can_delete_category(admin_client):
    category = Category.objects.create(name="Meat")
    url = reverse("category-detail", args=[category.id])
    response = admin_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Category.objects.filter(id=category.id).exists()


@pytest.mark.django_db
def test_non_admin_cannot_delete_category(user_client):
    category = Category.objects.create(name="Bakery")
    url = reverse("category-detail", args=[category.id])
    response = user_client.delete(url)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert Category.objects.filter(id=category.id).exists()