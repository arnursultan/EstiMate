from django.urls import path
from .views import (
    MyFinanceStatView, StoreFinanceView, ManualFinanceEntryView,
    AdminFinanceStatView, CalendarStatisticsView, ArchivedDataView,
    AdminDamagedGoodsReportView, BalanceCalculatorView, ProductRequestHistoryView,
    FinanceSummaryView, PartnerFinanceStatListView, StoreFinanceStatListView,
    FinanceEntryListView
)

app_name = 'finance'

urlpatterns = [
    # Партнерские маршруты
    path('my/', MyFinanceStatView.as_view(), name='my-finance'),
    path('manual/', ManualFinanceEntryView.as_view(), name='manual-finance'),
    path('manual/list/', FinanceEntryListView.as_view(), name='finance-entry-list'),
    path('balance/', BalanceCalculatorView.as_view(), name='balance-calculator'),
    path('history/requests/', ProductRequestHistoryView.as_view(), name='request-history'),
    path('summary/', FinanceSummaryView.as_view(), name='finance-summary'),
    path('calendar/', CalendarStatisticsView.as_view(), name='calendar-statistics'),
    path('archives/', ArchivedDataView.as_view(), name='archived-data'),

    # Административные маршруты
    path('admin/finance-stat/', AdminFinanceStatView.as_view(), name='admin-finance-stat'),
    path('admin/damaged-report/', AdminDamagedGoodsReportView.as_view(), name='damaged-goods-report'),
    path('admin/stores/', StoreFinanceView.as_view(), name='store-finance'),

    # Сериализаторы моделей
    path('partner-stats/', PartnerFinanceStatListView.as_view(), name='partner-finance'),
    path('store-stats/', StoreFinanceStatListView.as_view(), name='store-finance-stats'),
]