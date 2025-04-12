from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers
from .views import (
    OrderViewSet,
    OrderItemViewSet,
    DefectItemViewSet,
    StoreDebtPaymentViewSet,
    StoreExpenseViewSet
)

# Основной роутер
router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'defects', DefectItemViewSet, basename='defect')
router.register(r'debt-payments', StoreDebtPaymentViewSet, basename='debt-payment')
router.register(r'expenses', StoreExpenseViewSet, basename='expense')

# Вложенный роутер для элементов заказа
order_items_router = routers.NestedSimpleRouter(router, r'orders', lookup='order')
order_items_router.register(r'items', OrderItemViewSet, basename='order-items')

# Вложенный роутер для бракованных товаров в заказе
order_defects_router = routers.NestedSimpleRouter(router, r'orders', lookup='order')
order_defects_router.register(r'defects', DefectItemViewSet, basename='order-defects')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(order_items_router.urls)),
    path('', include(order_defects_router.urls)),
]