import pytest
from django.urls import reverse
from apps.stores.models import Store, City
from apps.users.models import User
from apps.notifications.models import Notification
from rest_framework.test import APIClient

@pytest.fixture
def partner_user():
    return User.objects.create_user(
        email="partner@example.com",
        password="Partner1234",
        phone="+996700000012",
        first_name="Partner",
        last_name="User",
        status="approved"
    )

@pytest.fixture
def partner_client(partner_user):
    client = APIClient()
    client.force_authenticate(user=partner_user)
    return client

@pytest.fixture
def city():
    return City.objects.create(name="Test City")

@pytest.fixture
def admin_user():
    return User.objects.create_superuser(
        email="admin@example.com",
        phone="+996700000000",
        first_name="Admin",
        last_name="User",
        password="adminpass123"
    )




@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client



@pytest.mark.django_db
def test_notify_admins_and_creator_on_approval(admin_user, partner_user, city):
    store = Store.objects.create(
        name="TestStore",
        inn="1234567890",
        city=city,
        address="Somewhere",
        phone="+996700000000",
        status="pending",
        creator=partner_user
    )

    # Обновляем статус магазина на 'approved'
    store.status = "approved"
    store.save()

    # Проверка уведомлений
    admin_notifications = Notification.objects.filter(recipient=admin_user, title__icontains="Магазин одобрен")
    creator_notifications = Notification.objects.filter(recipient=partner_user, title__icontains="Ваш магазин одобрен")

    assert admin_notifications.exists()
    assert creator_notifications.exists()


@pytest.mark.django_db
def test_notify_admins_and_creator_on_rejection(admin_user, partner_user, city):
    store = Store.objects.create(
        name="RejectStore",
        inn="2234567890",
        city=city,
        address="Nowhere",
        phone="+996700000001",
        status="pending",
        creator=partner_user
    )

    # Обновляем статус на 'rejected'
    store.status = "rejected"
    store.save()

    admin_notifications = Notification.objects.filter(recipient=admin_user, title__icontains="Магазин отклонён")
    creator_notifications = Notification.objects.filter(recipient=partner_user, title__icontains="Ваш магазин отклонен")

    assert admin_notifications.exists()
    assert creator_notifications.exists()
