from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CityViewSet, StoreViewSet, StoreDebtViewSet

router = DefaultRouter()
router.register(r'cities', CityViewSet)
router.register(r'stores', StoreViewSet)
router.register(r'debts', StoreDebtViewSet, basename='store-debt')
# Не менять  basename  иначе все тесты слетят


urlpatterns = [
    path('', include(router.urls)),
    path('debts/pay/', StoreDebtViewSet.as_view({'post': 'pay_debt'}), name='pay-debt'),
]