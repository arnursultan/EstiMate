import pytest
from rest_framework.test import APIRequestFactory
from apps.users.models import User
from apps.products.views import IsAdminUser

factory = APIRequestFactory()

@pytest.mark.django_db
def test_admin_user_has_permission():
    user = User.objects.create_user(
        email="admin@example.com",
        phone="+996700000001",
        password="Admin1234",
        first_name="Admin",
        last_name="Test",
        is_staff=True
    )
    request = factory.get('/fake-url/')
    request.user = user
    permission = IsAdminUser()

    assert permission.has_permission(request, None) is True


@pytest.mark.django_db
def test_non_admin_user_no_permission():
    user = User.objects.create_user(
        email="user@example.com",
        phone="+996700000002",
        password="User1234",
        first_name="Normal",
        last_name="User",
        is_staff=False
    )
    request = factory.get('/fake-url/')
    request.user = user
    permission = IsAdminUser()

    assert permission.has_permission(request, None) is False


@pytest.mark.django_db
def test_anonymous_user_no_permission():
    request = factory.get('/fake-url/')
    request.user = None
    permission = IsAdminUser()

    assert permission.has_permission(request, None) is False
