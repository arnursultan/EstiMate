from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderRequestViewSet

router = DefaultRouter()
router.register(r'order-requests', OrderRequestViewSet, basename="order-request")

urlpatterns = [
    path("", include(router.urls)),
]
