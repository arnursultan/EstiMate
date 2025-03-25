from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CityViewSet, StoreViewSet, StoreDebtViewSet

router = DefaultRouter()
router.register(r'cities', CityViewSet)
router.register(r'stores', StoreViewSet)
router.register(r'store-debts', StoreDebtViewSet)

urlpatterns = [
    path('', include(router.urls)),
]