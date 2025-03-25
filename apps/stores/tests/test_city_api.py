import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.stores.models import City
from apps.users.models import User

CITIES_URL = reverse("city-list")

@pytest.fixture
def client():
    return APIClient()

@pytest.fixture
def user():
    return User.objects.create_user(
        email="user@example.com",
        phone="+996700000001",
        password="Test1234",
        first_name="Test",
        last_name="User",
        status="approved"
    )

@pytest.fixture
def admin_user():
    return User.objects.create_superuser(
        email="admin@example.com",
        phone="+996700000002",
        password="Admin1234",
        first_name="Admin",
        last_name="User"
    )

@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client

@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(admin_user)
    return client

@pytest.mark.django_db
def test_get_city_list_unauthorized(client):
    response = client.get(CITIES_URL)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.django_db
def test_get_city_list_authorized(auth_client):
    City.objects.create(name="Bishkek")
    City.objects.create(name="Osh")
    response = auth_client.get(CITIES_URL)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 2
    assert response.data[0]["name"] in ["Bishkek", "Osh"]

@pytest.mark.django_db
def test_create_city_admin_only(admin_client, auth_client):
    # ✅ Админ может создать
    response = admin_client.post(CITIES_URL, {"name": "Karakol"})
    assert response.status_code == status.HTTP_201_CREATED
    assert City.objects.filter(name="Karakol").exists()

    # ❌ Не-админ не может
    response = auth_client.post(CITIES_URL, {"name": "Jalal-Abad"})
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
def test_create_city_invalid_data(admin_client):
    response = admin_client.post(CITIES_URL, {"name": ""})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "name" in response.data

@pytest.mark.django_db
def test_search_city(auth_client):
    City.objects.create(name="Bishkek")
    City.objects.create(name="Karakol")
    City.objects.create(name="Osh")
    response = auth_client.get(f"{CITIES_URL}?search=karak")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["name"] == "Karakol"

@pytest.mark.django_db
def test_ordering_city(auth_client):
    City.objects.create(name="Osh")
    City.objects.create(name="Bishkek")
    City.objects.create(name="Karakol")
    response = auth_client.get(f"{CITIES_URL}?ordering=name")
    names = [city["name"] for city in response.data]
    assert names == sorted(names)


@pytest.mark.django_db
def test_admin_can_update_city(admin_client):
    city = City.objects.create(name="Old Name")
    url = reverse("city-detail", args=[city.id])
    response = admin_client.patch(url, {"name": "New Name"})
    assert response.status_code == status.HTTP_200_OK
    city.refresh_from_db()
    assert city.name == "New Name"


@pytest.mark.django_db
def test_admin_can_delete_city(admin_client):
    city = City.objects.create(name="ToDelete")
    url = reverse("city-detail", args=[city.id])
    response = admin_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not City.objects.filter(id=city.id).exists()


@pytest.mark.django_db
def test_user_cannot_update_or_delete_city(auth_client):
    city = City.objects.create(name="Protected")
    url = reverse("city-detail", args=[city.id])

    patch = auth_client.patch(url, {"name": "Hack"})
    delete = auth_client.delete(url)

    assert patch.status_code == status.HTTP_403_FORBIDDEN
    assert delete.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_create_city_duplicate_name(admin_client):
    City.objects.create(name="Naryn")
    response = admin_client.post(CITIES_URL, {"name": "Naryn"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "name" in response.data


@pytest.mark.django_db
def test_admin_can_update_city(admin_client):
    city = City.objects.create(name="OldName")
    url = reverse("city-detail", args=[city.id])

    # PUT
    response = admin_client.put(url, {"name": "NewName"})
    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "NewName"

    # PATCH
    response = admin_client.patch(url, {"name": "PatchedName"})
    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "PatchedName"


@pytest.mark.django_db
def test_admin_can_delete_city(admin_client):
    city = City.objects.create(name="ToDelete")
    url = reverse("city-detail", args=[city.id])
    response = admin_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not City.objects.filter(id=city.id).exists()


@pytest.mark.django_db
def test_non_admin_cannot_modify_city(auth_client):
    city = City.objects.create(name="SecureCity")
    url = reverse("city-detail", args=[city.id])

    put = auth_client.put(url, {"name": "HackCity"})
    patch = auth_client.patch(url, {"name": "HackCity"})
    delete = auth_client.delete(url)

    assert put.status_code == status.HTTP_403_FORBIDDEN
    assert patch.status_code == status.HTTP_403_FORBIDDEN
    assert delete.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_search_city_no_results(auth_client):
    City.objects.create(name="Karakol")
    response = auth_client.get(f"{CITIES_URL}?search=Nowhere")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 0


@pytest.mark.django_db
def test_search_city_case_insensitive(auth_client):
    City.objects.create(name="Bishkek")
    response = auth_client.get(f"{CITIES_URL}?search=BISHKEK")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
