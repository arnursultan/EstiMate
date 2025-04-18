from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet, PartnerInventoryViewSet

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'inventory', PartnerInventoryViewSet, basename='inventory')

urlpatterns = [
    path('', include(router.urls)),
    path('my-inventory/', ProductViewSet.as_view({'get': 'available_products_for_store'}), name='my-inventory'),
    path('products-for-admin-orders/', ProductViewSet.as_view({'get': 'products_for_admin_orders'}), name='products-for-admin-orders'),
    path('products-for-store-orders/', ProductViewSet.as_view({'get': 'products_for_store_orders'}), name='products-for-store-orders'),
]