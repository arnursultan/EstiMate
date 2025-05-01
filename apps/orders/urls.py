# apps/orders/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers
from .views import (
    OrderViewSet,
    OrderItemViewSet,
    DefectItemViewSet,
    # StoreDebtPaymentViewSet - ПЕРЕМЕЩЕН
    # StoreExpenseViewSet - УДАЛЕН
)

# Основной роутер для заказов и общих дефектов
router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='order')
# Общий доступ к дефектам (например, для админа)
router.register(r'defects', DefectItemViewSet, basename='defect')
# Платежи и расходы ПЕРЕМЕЩЕНЫ в stores

# Вложенный роутер для элементов заказа: /orders/{order_pk}/items/
order_items_router = routers.NestedSimpleRouter(router, r'orders', lookup='order')
order_items_router.register(r'items', OrderItemViewSet, basename='order-items')

# Вложенный роутер для бракованных товаров в заказе: /orders/{order_pk}/defects/
order_defects_router = routers.NestedSimpleRouter(router, r'orders', lookup='order')
order_defects_router.register(r'defects', DefectItemViewSet, basename='order-defects')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(order_items_router.urls)),
    path('', include(order_defects_router.urls)),
    # Дополнительные actions из OrderViewSet, если они не вложенные
    path('orders/statistics/', OrderViewSet.as_view({'get': 'statistics'}), name='order-statistics'),
    path('orders/admin-orders/', OrderViewSet.as_view({'get': 'admin_orders'}), name='admin-orders'),
    path('orders/store-orders/', OrderViewSet.as_view({'get': 'store_orders'}), name='store-orders'),
    path('orders/in-process/', OrderViewSet.as_view({'get': 'in_process'}), name='in-process-orders'),
    path('orders/get-store-orders/', OrderViewSet.as_view({'get': 'get_store_orders'}), name='get-store-orders-by-date'),
    # Дополнительные actions из DefectItemViewSet
    path('defects/add-group/', DefectItemViewSet.as_view({'post': 'add_group'}), name='defect-add-group'), # Хотя это лучше делать через вложенный
    path('defects/order-defects/', DefectItemViewSet.as_view({'get': 'order_defects'}), name='get-order-defects'),
    path('defects/store-defects/', DefectItemViewSet.as_view({'get': 'store_defects'}), name='get-store-defects'),

]