import io

import pytest
from PIL import Image
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.products.models import Product, Category
from apps.users.models import User

PRODUCTS_URL = reverse("product-list")

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
def user():
    return User.objects.create_user(
        email="user@example.com",
        password="User123",
        phone="+996700000002",
        first_name="Test",
        last_name="User",
        status="approved"
    )

@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client

@pytest.fixture
def user_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client

@pytest.fixture
def category():
    return Category.objects.create(name="Beverages")

@pytest.fixture
def product(category):
    return Product.objects.create(
        name="Cola", category=category, description="Cool drink", price=100, quantity=10
    )

@pytest.mark.django_db
def test_list_products(user_client, product):
    response = user_client.get(PRODUCTS_URL)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) >= 1

@pytest.mark.django_db
def test_create_product_admin_only(admin_client, user_client, category):
    data = {
        "name": "Fanta", "category": category.id,
        "description": "Orange soda", "price": 120, "quantity": 20
    }
    # ✅ Админ может создать
    response = admin_client.post(PRODUCTS_URL, data)
    assert response.status_code == status.HTTP_201_CREATED

    # ❌ Обычный пользователь не может
    response = user_client.post(PRODUCTS_URL, data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
def test_get_product_detail(user_client, product):
    url = reverse("product-detail", args=[product.id])
    response = user_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == product.name

@pytest.mark.django_db
def test_product_not_found(user_client):
    url = reverse("product-detail", args=[999])
    response = user_client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.django_db
def test_update_product(admin_client, product):
    url = reverse("product-detail", args=[product.id])
    response = admin_client.patch(url, {"price": 150})
    assert response.status_code == status.HTTP_200_OK
    product.refresh_from_db()
    assert product.price == 150

@pytest.mark.django_db
def test_delete_product(admin_client, product):
    url = reverse("product-detail", args=[product.id])
    response = admin_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT

@pytest.mark.django_db
def test_add_quantity_success(admin_client, product):
    url = reverse("product-add-quantity", args=[product.id])
    response = admin_client.post(url, {"quantity_to_add": 5})
    assert response.status_code == status.HTTP_200_OK
    product.refresh_from_db()
    assert product.quantity == 15

@pytest.mark.django_db
def test_add_quantity_invalid(admin_client, product):
    url = reverse("product-add-quantity", args=[product.id])
    response = admin_client.post(url, {"quantity_to_add": -10})
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    response = admin_client.post(url, {"quantity_to_add": "abc"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST

@pytest.mark.django_db
def test_add_quantity_user_forbidden(user_client, product):
    url = reverse("product-add-quantity", args=[product.id])
    response = user_client.post(url, {"quantity_to_add": 5})
    assert response.status_code == status.HTTP_403_FORBIDDEN



@pytest.mark.django_db
def test_created_at_read_only(admin_client, category):
    product = Product.objects.create(
        name="Test Product",
        category=category,
        description="Some product",
        price=100,
        quantity=10
    )
    url = reverse("product-detail", args=[product.id])

    original_created_at = product.created_at

    # Пытаемся изменить created_at
    response = admin_client.patch(url, {"created_at": "2000-01-01T00:00:00Z"})

    assert response.status_code == status.HTTP_200_OK
    product.refresh_from_db()
    assert product.created_at == original_created_at



@pytest.fixture
def image_file():
    file = io.BytesIO()
    image = Image.new("RGB", (100, 100), "blue")
    image.save(file, "jpeg")
    file.name = "test.jpg"
    file.seek(0)
    return file


@pytest.mark.django_db
def test_create_product_with_image(admin_client, category, image_file):
    url = reverse("product-list")
    data = {
        "name": "Sprite",
        "category": category.id,
        "description": "Lemon soda",
        "price": 100,
        "quantity": 10,
        "image": image_file,
    }
    response = admin_client.post(url, data, format="multipart")
    assert response.status_code == status.HTTP_201_CREATED
    assert "image" in response.data
    assert response.data["image"].endswith(".jpg")


@pytest.mark.django_db
def test_update_product_image(admin_client, category, image_file):
    product = Product.objects.create(
        name="Juice", category=category, description="Fruit juice", price=50, quantity=5
    )
    url = reverse("product-detail", args=[product.id])
    response = admin_client.patch(
        url, {"image": image_file}, format="multipart"
    )
    assert response.status_code == status.HTTP_200_OK
    product.refresh_from_db()
    assert "test" in product.image.name
    assert product.image.name.endswith(".jpg")


@pytest.mark.django_db
@pytest.mark.parametrize("field, value", [
    ("name", ""),
    ("price", -100),
    ("quantity", -5),
    ("description", ""),
])
def test_invalid_product_fields(admin_client, category, field, value):
    data = {
        "name": "Product X",
        "category": category.id,
        "description": "Description",
        "price": 100,
        "quantity": 10
    }
    data[field] = value
    url = reverse("product-list")
    response = admin_client.post(url, data, format="multipart")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field in response.data