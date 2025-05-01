# apps/products/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet, PartnerInventoryViewSet # ДОБАВЛЕН PartnerInventoryViewSet

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'inventory', PartnerInventoryViewSet, basename='inventory') # ДОБАВЛЕНА регистрация

urlpatterns = [
    path('', include(router.urls)),
    # Actions из ProductViewSet
    path('products/admin-orders/', ProductViewSet.as_view({'get': 'products_for_admin_orders'}), name='products-for-admin-orders'),
    path('products/store-orders/', ProductViewSet.as_view({'get': 'products_for_store_orders'}), name='products-for-store-orders'),
    # Actions из PartnerInventoryViewSet (если есть кастомные)
    path('inventory/available/', PartnerInventoryViewSet.as_view({'get': 'available_products'}), name='inventory-available'),
]