from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CityViewSet,
    StoreViewSet,
    StoreDebtViewSet
)

router = DefaultRouter()
router.register(r'cities', CityViewSet, basename='city')
router.register(r'stores', StoreViewSet, basename='store')
router.register(r'debts', StoreDebtViewSet, basename='store-debt')

urlpatterns = [
    path('', include(router.urls)),
]