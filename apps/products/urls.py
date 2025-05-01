# apps/products/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProductViewSet,
    PartnerInventoryListView, # View для админа
    MyInventoryListView,      # View для партнера
    # Убрали импорт AdminPartnerInventoryViewSet, если он не используется
)

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
# НЕ регистрируем здесь PartnerInventoryListView и MyInventoryListView, т.к. у них кастомные URL

urlpatterns = [
    # URL'ы от роутера для ProductViewSet (/api/products/products/, /api/products/products/{pk}/, etc.)
    path('', include(router.urls)),

    # --- Путь для инвентаря КОНКРЕТНОГО партнера (для админа) ---
    # Префикс 'inventory/partner/' делает URL уникальным
    path('inventory/partner/<int:partner_pk>/', PartnerInventoryListView.as_view(), name='partner-inventory-list'),

    # --- Путь для СВОЕГО инвентаря (для партнера) ---
    path('my-inventory/', MyInventoryListView.as_view(), name='my-inventory-list'),

    # Actions из ProductViewSet (доступны через /api/products/products/...)
    # Перенесем их сюда для ясности, хотя router их тоже создает
    path('products/admin-orders/', ProductViewSet.as_view({'get': 'products_for_admin_orders'}), name='products-for-admin-orders-action'),
    path('products/store-orders/', ProductViewSet.as_view({'get': 'products_for_store_orders'}), name='products-for-store-orders-action'),

    # Опционально: Actions для ProductViewSet, которые не создаются роутером по умолчанию (если такие есть)
    # path('products/<int:pk>/activate/', ProductViewSet.as_view({'post': 'activate'}), name='product-activate'), # Пример - роутер это тоже может делать
]