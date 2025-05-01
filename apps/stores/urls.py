# apps/stores/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers # Импортируем, если нужны вложенные для платежей/долгов
from .views import (
    CityViewSet,
    StoreViewSet,
    StoreDebtViewSet, # Добавляем, если он был в отдельном файле или не было роутера
    StoreDebtPaymentViewSet,
    StoresSummaryStatisticsView# ДОБАВЛЕН
    # StoreExpenseViewSet - УДАЛЕН
)

# Основной роутер
router = DefaultRouter()
router.register(r'cities', CityViewSet, basename='city')
router.register(r'stores', StoreViewSet, basename='store')
router.register(r'debts', StoreDebtViewSet, basename='store-debt') # Регистрируем долги
router.register(r'debt-payments', StoreDebtPaymentViewSet, basename='debt-payment') # Регистрируем платежи
# StoreExpenseViewSet - УДАЛЕН

# --- Пример вложенных роутеров (если нужно) ---
# # Вложенный роутер для долгов магазина: /stores/{store_pk}/debts/
# store_debts_router = routers.NestedSimpleRouter(router, r'stores', lookup='store')
# store_debts_router.register(r'debts', StoreDebtViewSet, basename='store-debts')
#
# # Вложенный роутер для платежей магазина: /stores/{store_pk}/payments/
# store_payments_router = routers.NestedSimpleRouter(router, r'stores', lookup='store')
# store_payments_router.register(r'payments', StoreDebtPaymentViewSet, basename='store-payments')
# --- Конец примера ---

urlpatterns = [
    path('', include(router.urls)),
    # --- Если используются вложенные роутеры ---
    # path('', include(store_debts_router.urls)),
    # path('', include(store_payments_router.urls)),
    # --- Конец ---
    path('stores-summary-statistics/', StoresSummaryStatisticsView.as_view(), name='stores-summary-statistics'),
    # Дополнительные actions, если они не вложенные
    path('stores/summary/', StoreViewSet.as_view({'get': 'stores_summary'}), name='stores-summary'), # Упрощенный вариант
    path('stores/city-summary/', StoreViewSet.as_view({'get': 'city_summary'}), name='city-summary'), # Упрощенный вариант
    path('stores/with-debt/', StoreViewSet.as_view({'get': 'with_debt'}), name='stores-with-debt'),
    path('stores/merge/', StoreViewSet.as_view({'post': 'merge_stores'}), name='merge-stores'), # Action для слияния
    # Если нужны actions для debt и payment, они должны быть в их ViewSet'ах и зарегистрированы здесь или в роутере
    path('debts/store-debts/', StoreDebtViewSet.as_view({'get': 'store_debts'}), name='get-store-debts'),
    path('debt-payments/store-payments/', StoreDebtPaymentViewSet.as_view({'get': 'store_payments'}), name='get-store-payments'),

]

