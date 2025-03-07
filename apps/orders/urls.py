from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderRequestViewSet

router = DefaultRouter()
router.register(r'orders', OrderRequestViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
