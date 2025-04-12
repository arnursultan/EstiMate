from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CityViewSet,
    StoreViewSet,
    StoreDebtViewSet,
    # StoreStatisticsView,
    # StoresStatisticsView
)

router = DefaultRouter()
router.register(r'cities', CityViewSet, basename='city')
router.register(r'stores', StoreViewSet, basename='store')
router.register(r'debts', StoreDebtViewSet, basename='store-debt')

urlpatterns = [
    path('', include(router.urls)),
    path('stores-summary/', StoreViewSet.as_view({'get': 'stores_summary'}), name='stores-summary'),
    path('city-summary/', StoreViewSet.as_view({'get': 'city_summary'}), name='city-summary'),
    # path('statistics/', StoresStatisticsView.as_view(), name='stores-statistics'),
    # path('<int:pk>/statistics/', StoreStatisticsView.as_view(), name='store-statistics'),
]