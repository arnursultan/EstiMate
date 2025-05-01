# apps/finance/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter # Импорт
from .views import (
    PartnerStatisticsView,
    AdminFinanceStatisticsView,
    AdminPartnersStatisticsView,
    PartnerExpenseViewSet # ДОБАВЛЕН импорт
)

app_name = 'finance'

# --- ДОБАВЛЕН РОУТЕР ---
router = DefaultRouter()
router.register(r'partner-expenses', PartnerExpenseViewSet, basename='partner-expenses')
# --- КОНЕЦ ---

urlpatterns = [
    path('', include(router.urls)), # Включаем URL'ы из роутера
    path('partner-statistics/', PartnerStatisticsView.as_view(), name='partner-statistics'),
    # Уберем pk, т.к. он определяется внутри view
    # path('partner-statistics/<int:pk>/', PartnerStatisticsView.as_view(), name='partner-statistics-detail'),
    path('admin-statistics/', AdminFinanceStatisticsView.as_view(), name='admin-statistics'),
    path('admin-partners-statistics/', AdminPartnersStatisticsView.as_view(), name='admin-partners-statistics'),
]