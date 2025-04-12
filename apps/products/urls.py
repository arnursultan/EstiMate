from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet, PartnerInventoryViewSet

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'inventory', PartnerInventoryViewSet, basename='inventory')

urlpatterns = [
    path('', include(router.urls)),
]