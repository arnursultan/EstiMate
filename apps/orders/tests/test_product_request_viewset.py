import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.products.models import PartnerProduct
from apps.orders.models import ProductRequest
from apps.stores.models import Store



@pytest.fixture
def admin():
    return User.objects.create_user(
        email="admin@example.com",
        password="Admin123",
        first_name="Admin",
        last_name="User",
        phone="+996700000001",
        is_staff=True
    )


@pytest.fixture
def partner():
    return User.objects.create_user(
        email="partner@example.com",
        password="Partner123",
        first_name="Partner",
        last_name="User",
        phone="+996700000002",
        status="approved"
    )


@pytest.fixture
def admin_client(admin):
    client = APIClient()
    client.force_authenticate(user=admin)
    return client


@pytest.fixture
def partner_client(partner):
    client = APIClient()
    client.force_authenticate(user=partner)
    return client




@pytest.fixture
def product():
    from apps.products.models import Product
    return Product.objects.create(
        name="Bonaqua",
        price=50,
        quantity=100,
        is_active=True
    )


@pytest.fixture
def store(partner, city):
    return Store.objects.create(
        name="My Store",
        inn="123456789012",
        address="Main Street",
        phone="+996777777777",
        city=city,
        creator=partner,
        is_active=True,
        status = "approved"
    )


@pytest.fixture
def city():
    from apps.stores.models import City
    return City.objects.create(name="Bishkek")

@pytest.fixture
def partner_product(partner, product):
    return PartnerProduct.objects.create(
        partner=partner,
        product=product,
        quantity=30,
        bonus_quantity=5,
        price=50.0
    )


@pytest.mark.django_db
def test_create_self_request_success(partner_client, product):
    url = reverse("product-requests-create-self-request")

    data = {
        'product_id': product.id,
        'quantity': 5
    }

    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['product'] == product.id
    assert response.data['quantity'] == 5
    assert response.data['status'] == 'pending'

@pytest.mark.django_db
def test_create_self_request_insufficient_quantity(partner_client, product):
    product.quantity = 2
    product.save()

    url = reverse("product-requests-create-self-request")
    data = {'product_id': product.id, 'quantity': 5}

    response = partner_client.post(url, data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Недостаточно товара" in str(response.data)


@pytest.mark.django_db
def test_create_self_request_invalid_product(partner_client):
    url = reverse("product-requests-create-self-request")
    data = {'product_id': 9999, 'quantity': 1}

    response = partner_client.post(url, data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "не найден" in str(response.data)


@pytest.mark.django_db
def test_create_self_request_negative_quantity(partner_client, product):
    url = reverse("product-requests-create-self-request")
    data = {'product_id': product.id, 'quantity': -3}

    response = partner_client.post(url, data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "quantity" in response.data
    assert response.data["quantity"][0].code == "min_value"


@pytest.mark.django_db
def test_create_self_request_zero_quantity(partner_client, product):
    url = reverse("product-requests-create-self-request")
    data = {'product_id': product.id, 'quantity': 0}

    response = partner_client.post(url, data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "quantity" in response.data
    assert response.data["quantity"][0].code == "min_value"


@pytest.mark.django_db
def test_create_self_request_missing_quantity(partner_client, product):
    url = reverse("product-requests-create-self-request")
    data = {'product_id': product.id}  # no quantity

    response = partner_client.post(url, data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "quantity" in response.data


@pytest.mark.django_db
def test_create_self_request_missing_product_id(partner_client):
    url = reverse("product-requests-create-self-request")
    data = {'quantity': 2}

    response = partner_client.post(url, data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "product_id" in response.data


@pytest.mark.django_db
def test_create_store_request_success(partner_client, partner_product, store):
    url = reverse("product-requests-create-store-request")
    data = {
        "partner_product_id": partner_product.id,
        "store_id": store.id,
        "quantity": 5
    }

    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["quantity"] == 5
    assert response.data["request_type"] == "STORE"
    assert response.data["status"] == "approved"


@pytest.mark.django_db
def test_create_store_request_insufficient_quantity(partner_client, partner_product, store):
    url = reverse("product-requests-create-store-request")
    data = {
        "partner_product_id": partner_product.id,
        "store_id": store.id,
        "quantity": partner_product.remaining_quantity + 10
    }

    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Недостаточно товара" in str(response.data)



@pytest.mark.django_db
def test_create_store_request_foreign_partner_product(admin_client, partner_product, store):
    url = reverse("product-requests-create-store-request")
    data = {
        "partner_product_id": partner_product.id,
        "store_id": store.id,
        "quantity": 1
    }

    response = admin_client.post(url, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "товар не найден" in str(response.data)


@pytest.mark.django_db
def test_create_store_request_invalid_store(partner_client, partner_product):
    url = reverse("product-requests-create-store-request")
    data = {
        "partner_product_id": partner_product.id,
        "store_id": 9999,
        "quantity": 1
    }

    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "магазин не найден" in str(response.data)


@pytest.mark.django_db
def test_create_store_request_inactive_store(partner_client, partner_product, city):
    from apps.stores.models import Store

    inactive_store = Store.objects.create(
        name="Inactive Store",
        inn="123123123123",
        address="Test",
        phone="+996700000099",
        city=city,
        creator=partner_product.partner,
        is_active=False,
        status="rejected"
    )

    url = reverse("product-requests-create-store-request")
    data = {
        "partner_product_id": partner_product.id,
        "store_id": inactive_store.id,
        "quantity": 1
    }

    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "не найден" in str(response.data) or "не активен" in str(response.data)



@pytest.mark.django_db
def test_create_store_request_negative_quantity(partner_client, partner_product, store):
    url = reverse("product-requests-create-store-request")
    data = {
        "partner_product_id": partner_product.id,
        "store_id": store.id,
        "quantity": -3
    }

    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "quantity" in response.data


@pytest.mark.django_db
def test_create_store_request_missing_fields(partner_client, partner_product):
    url = reverse("product-requests-create-store-request")
    data = {
        "partner_product_id": partner_product.id,
        # store_id is missing
        "quantity": 1
    }

    response = partner_client.post(url, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "store_id" in response.data


@pytest.mark.django_db
def test_group_self_request_success(partner_client, product):
    url = reverse("product-requests-group-self-request")
    data = {
        "items": [
            {"product_id": product.id, "quantity": 5}
        ]
    }

    response = partner_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert "created_requests" in response.data
    assert response.data["total_items"] == 1


@pytest.mark.django_db
def test_group_self_request_insufficient_quantity(partner_client, product):
    product.quantity = 3
    product.save()

    url = reverse("product-requests-group-self-request")
    data = {
        "items": [
            {"product_id": product.id, "quantity": 10}
        ]
    }

    response = partner_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Недостаточно товара" in str(response.data)


@pytest.mark.django_db
def test_group_self_request_invalid_product(partner_client):
    url = reverse("product-requests-group-self-request")
    data = {
        "items": [
            {"product_id": 9999, "quantity": 1}
        ]
    }

    response = partner_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "не найден" in str(response.data)



@pytest.mark.django_db
def test_group_self_request_all_invalid(partner_client):
    url = reverse("product-requests-group-self-request")
    data = {
        "items": [
            {"product_id": 9999, "quantity": 1},
            {"product_id": 8888, "quantity": 2}
        ]
    }

    response = partner_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Не удалось создать ни один запрос" in str(response.data)


@pytest.mark.django_db
def test_group_self_request_empty_items(partner_client):
    url = reverse("product-requests-group-self-request")
    data = {
        "items": []
    }

    response = partner_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Необходимо указать хотя бы один товар" in str(response.data)


@pytest.mark.django_db
def test_group_self_request_negative_quantity(partner_client, product):
    url = reverse("product-requests-group-self-request")
    data = {
        "items": [
            {"product_id": product.id, "quantity": -1}
        ]
    }

    response = partner_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Количество должно быть положительным" in str(response.data)


@pytest.mark.django_db
def test_group_self_request_missing_product_id(partner_client):
    url = reverse("product-requests-group-self-request")
    data = {
        "items": [{"quantity": 5}]
    }

    response = partner_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Не указан ID товара" in str(response.data)


@pytest.mark.django_db
def test_group_self_request_missing_items_field(partner_client):
    url = reverse("product-requests-group-self-request")
    data = {}

    response = partner_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Необходимо указать хотя бы один товар" in str(response.data)


@pytest.mark.django_db
def test_group_store_request_success(partner_client, partner_product, store):
    url = reverse("product-requests-group-store-request")
    data = {
        "store_id": store.id,
        "items": [
            {"partner_product_id": partner_product.id, "quantity": 2},
            {"partner_product_id": partner_product.id, "quantity": 1}
        ]
    }
    response = partner_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert len(response.data["created_requests"]) == 2
    assert response.data["errors"] == []


@pytest.mark.django_db
def test_group_store_request_partial_success(partner_client, partner_product, store):
    url = reverse("product-requests-group-store-request")
    data = {
        "store_id": store.id,
        "items": [
            {"partner_product_id": 9999, "quantity": 2},  # ❌ не существует
            {"partner_product_id": partner_product.id, "quantity": 3}  # ✅ валидный
        ]
    }
    response = partner_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert "created_requests" in response.data
    assert len(response.data["created_requests"]) == 1
    assert "errors" in response.data
    assert len(response.data["errors"]) == 1


@pytest.mark.django_db
def test_group_store_request_all_invalid(partner_client, store):
    url = reverse("product-requests-group-store-request")
    data = {
        "store_id": store.id,
        "items": [
            {"partner_product_id": 9999, "quantity": -5},
            {"partner_product_id": 9999, "quantity": 0},
        ]
    }
    response = partner_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "error" in response.data
    assert "Не удалось создать ни один запрос" in response.data["error"]



@pytest.mark.django_db
def test_group_store_request_insufficient_quantity(partner_client, partner_product, store):
    url = reverse("product-requests-group-store-request")
    data = {
        "store_id": store.id,
        "items": [{
            "partner_product_id": partner_product.id,
            "quantity": partner_product.remaining_quantity + 10
        }]
    }
    response = partner_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Недостаточно товара" in str(response.data["details"][0]["error"])


@pytest.mark.django_db
def test_group_store_request_invalid_partner_product(partner_client, store):
    url = reverse("product-requests-group-store-request")
    data = {
        "store_id": store.id,
        "items": [{
            "partner_product_id": 9999,
            "quantity": 2
        }]
    }
    response = partner_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "не найден" in str(response.data["details"][0]["error"])



@pytest.mark.django_db
def test_group_store_request_missing_store_id(partner_client, partner_product):
    url = reverse("product-requests-group-store-request")
    data = {
        "items": [{
            "partner_product_id": partner_product.id,
            "quantity": 2
        }]
    }
    response = partner_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Необходимо указать ID магазина" in str(response.data["error"])


@pytest.mark.django_db
def test_group_store_request_missing_items(partner_client, store):
    url = reverse("product-requests-group-store-request")
    data = {
        "store_id": store.id,
        "items": []
    }
    response = partner_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Необходимо указать хотя бы один товар" in str(response.data["error"])


@pytest.mark.django_db
def test_group_store_request_negative_quantity(partner_client, partner_product, store):
    url = reverse("product-requests-group-store-request")
    data = {
        "store_id": store.id,
        "items": [{
            "partner_product_id": partner_product.id,
            "quantity": -5
        }]
    }
    response = partner_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "положительным числом" in str(response.data["details"][0]["error"])



@pytest.mark.django_db
def test_group_store_request_foreign_partner_product(admin_client, partner_product, store):
    url = reverse("product-requests-group-store-request")
    data = {
        "store_id": store.id,
        "items": [{
            "partner_product_id": partner_product.id,
            "quantity": 1
        }]
    }
    response = admin_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "не найден" in str(response.data["details"][0]["error"])


@pytest.mark.django_db
def test_confirm_receipt_success(partner_client, partner_product, store):
    # Создаём STORE-запрос в статусе approved
    request = ProductRequest.objects.create(
        product=partner_product.product,
        user=partner_product.partner,
        quantity=3,
        request_type="STORE",
        store=store,
        partner_product=partner_product,
        status="approved"
    )

    url = reverse("product-requests-confirm-receipt", args=[request.id])
    response = partner_client.post(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["request"]["status"] == "received"


@pytest.mark.django_db
def test_confirm_receipt_not_owner(admin_client, partner_product, store):
    request = ProductRequest.objects.create(
        product=partner_product.product,
        user=partner_product.partner,
        quantity=3,
        request_type="STORE",
        store=store,
        partner_product=partner_product,
        status="approved"
    )

    url = reverse("product-requests-confirm-receipt", args=[request.id])
    response = admin_client.post(url)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "только своих" in str(response.data["error"])


@pytest.mark.django_db
def test_confirm_receipt_invalid_status(partner_client, partner_product, store):
    request = ProductRequest.objects.create(
        product=partner_product.product,
        user=partner_product.partner,
        quantity=3,
        request_type="STORE",
        store=store,
        partner_product=partner_product,
        status="pending"
    )

    url = reverse("product-requests-confirm-receipt", args=[request.id])
    response = partner_client.post(url)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "не может быть отмечен как полученный" in str(response.data["error"])


@pytest.mark.django_db
def test_confirm_receipt_already_received(partner_client, partner_product, store):
    request = ProductRequest.objects.create(
        product=partner_product.product,
        user=partner_product.partner,
        quantity=3,
        request_type="STORE",
        store=store,
        partner_product=partner_product,
        status="received"
    )

    url = reverse("product-requests-confirm-receipt", args=[request.id])
    response = partner_client.post(url)

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_confirm_receipt_invalid_id(partner_client):
    url = reverse("product-requests-confirm-receipt", args=[9999])
    response = partner_client.post(url)

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_update_status_success(admin_client, partner, product):
    # создаём SELF-запрос от партнёра
    request = ProductRequest.objects.create(
        product=product,
        user=partner,
        quantity=2,
        request_type='SELF',
        status='pending'
    )

    url = reverse("product-requests-update-status", args=[request.id])
    data = {"status": "approved"}

    response = admin_client.patch(url, data, format='json')

    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "approved"


@pytest.mark.django_db
def test_update_status_for_store_request(admin_client, partner_product, store):
    request = ProductRequest.objects.create(
        product=partner_product.product,
        user=partner_product.partner,
        quantity=2,
        request_type='STORE',
        store=store,
        partner_product=partner_product,
        status='pending'
    )

    url = reverse("product-requests-update-status", args=[request.id])
    data = {"status": "approved"}

    response = admin_client.patch(url, data, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "только для запросов типа SELF" in str(response.data["error"])


@pytest.mark.django_db
def test_process_batch_approve_success(admin_client, partner, product):
    import uuid
    batch_id = uuid.uuid4()
    for _ in range(2):
        ProductRequest.objects.create(
            product=product,
            user=partner,
            quantity=1,
            request_type='SELF',
            status='pending',
            batch_id=batch_id
        )

    url = reverse("product-requests-process-batch")
    data = {
        "batch_id": str(batch_id),
        "status": "approved"
    }

    response = admin_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_200_OK
    assert response.data["processed_count"] == 2
    assert all(req["status"] == "approved" for req in response.data["processed"])


@pytest.mark.django_db
def test_process_batch_invalid_status(admin_client):
    url = reverse("product-requests-process-batch")
    data = {
        "batch_id": "fake-batch-id",
        "status": "unknown"
    }

    response = admin_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Статус может быть только" in str(response.data["error"])
