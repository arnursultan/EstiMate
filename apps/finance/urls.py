# Обновление файла apps/finance/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PartnerStatisticsView,
    AdminFinanceStatisticsView,
    AdminPartnersStatisticsView,
    PartnerExpenseViewSet  # Добавляем новое представление
)

app_name = 'finance'

router = DefaultRouter()
router.register(r'partner-expenses', PartnerExpenseViewSet, basename='partner-expenses')  # Добавляем новый маршрут

urlpatterns = [
    path('', include(router.urls)),  # Добавляем маршруты из router
    path('partner-statistics/', PartnerStatisticsView.as_view(), name='partner-statistics'),
    path('partner-statistics/<int:pk>/', PartnerStatisticsView.as_view(), name='partner-statistics-detail'),
    path('admin-statistics/', AdminFinanceStatisticsView.as_view(), name='admin-statistics'),
    path('admin-partners-statistics/', AdminPartnersStatisticsView.as_view(), name='admin-partners-statistics'),
]