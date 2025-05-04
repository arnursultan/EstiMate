# apps/orders/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers # Используем nested routers
from .views import (
    OrderViewSet,
    OrderItemViewSet,
    DefectItemViewSet
    # ViewSet'ы для платежей и расходов УДАЛЕНЫ отсюда
)

app_name = 'orders' # Добавим app_name для ясности

# --- Роутеры ---
# Основной роутер для Order и Defect (общий доступ)
router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'defects', DefectItemViewSet, basename='defect') # Эндпоинт для админа/общего списка

# Вложенный роутер для ЭЛЕМЕНТОВ заказа: /orders/{order_pk}/items/
order_items_router = routers.NestedSimpleRouter(router, r'orders', lookup='order')
order_items_router.register(r'items', OrderItemViewSet, basename='order-item') # Изменил basename

# Вложенный роутер для БРАКА в заказе: /orders/{order_pk}/defects/
order_defects_router = routers.NestedSimpleRouter(router, r'orders', lookup='order')
order_defects_router.register(r'defects', DefectItemViewSet, basename='order-defect') # Изменил basename

urlpatterns = [
    # Базовые URL'ы от основного роутера (/orders/, /orders/{pk}/, /defects/, /defects/{pk}/)
    path('', include(router.urls)),

    # Вложенные URL'ы для элементов заказа (/orders/{order_pk}/items/, /orders/{order_pk}/items/{pk}/)
    path('', include(order_items_router.urls)),

    # Вложенные URL'ы для брака заказа (/orders/{order_pk}/defects/, /orders/{order_pk}/defects/{pk}/)
    path('', include(order_defects_router.urls)),

    # --- Кастомные actions ---

    # Action для добавления брака по магазину/дате (НЕ вложенный)
    path('defects/add-group-by-store/', DefectItemViewSet.as_view({'post': 'add_group_by_store'}), name='defect-add-group-by-store'),

    # Actions для получения списков брака (НЕ вложенные)
    path('defects/order-defects/', DefectItemViewSet.as_view({'get': 'order_defects'}), name='get-order-defects'),
    path('defects/store-defects/', DefectItemViewSet.as_view({'get': 'store_defects'}), name='get-store-defects'),

    # Actions для OrderViewSet, если они не генерируются роутером или для удобства
    # path('orders/statistics/', OrderViewSet.as_view({'get': 'statistics'}), name='order-statistics'), # Генерируется роутером
    # path('orders/admin-orders/', OrderViewSet.as_view({'get': 'admin_orders'}), name='admin-orders'), # Генерируется роутером
    # path('orders/store-orders/', OrderViewSet.as_view({'get': 'store_orders'}), name='store-orders'), # Генерируется роутером
    # path('orders/in-process/', OrderViewSet.as_view({'get': 'in_process'}), name='in-process-orders'), # Генерируется роутером
    # path('orders/get-store-orders/', OrderViewSet.as_view({'get': 'get_store_orders'}), name='get-store-orders-by-date'), # Можно оставить для удобства или убрать
]