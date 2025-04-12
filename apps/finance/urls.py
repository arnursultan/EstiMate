from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PartnerFinanceEntryViewSet,
    StoreFinanceEntryViewSet,
    StatisticsViewSet
)

app_name = 'finance'

router = DefaultRouter()
router.register(r'partner-entries', PartnerFinanceEntryViewSet, basename='partner-finance')
router.register(r'store-entries', StoreFinanceEntryViewSet, basename='store-finance')
router.register(r'statistics', StatisticsViewSet, basename='statistics')

urlpatterns = [
    path('', include(router.urls)),
]