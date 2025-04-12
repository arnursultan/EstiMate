# apps/finance/urls.py
from django.urls import path
from .views import (
    PartnerStatisticsView,
    AdminFinanceStatisticsView,
    AdminPartnersStatisticsView
)

app_name = 'finance'

urlpatterns = [
    path('partner-statistics/', PartnerStatisticsView.as_view(), name='partner-statistics'),
    path('partner-statistics/<int:pk>/', PartnerStatisticsView.as_view(), name='partner-statistics-detail'),
    path('admin-statistics/', AdminFinanceStatisticsView.as_view(), name='admin-statistics'),
    path('admin-partners-statistics/', AdminPartnersStatisticsView.as_view(), name='admin-partners-statistics'),
]