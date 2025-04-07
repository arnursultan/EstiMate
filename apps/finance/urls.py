from django.urls import path
from .views import (
    MyFinanceStatView, StoreStatisticsView, ManualFinanceEntryView,
    AdminStatisticsView, CalendarStatisticsView, ArchivedDataView,
    AdminDamagedGoodsReportView, BalanceCalculatorView, ProductRequestHistoryView,
    FinanceSummaryView, StoreFinanceStatListView,
    FinanceEntryListView, PartnerInventoryView, FinanceEntryCreateView,
    PartnerProductFinanceView, PartnerCatalogFinanceView, PartnerStatisticsView
)

app_name = 'finance'

urlpatterns = [
    # Партнерские маршруты
    path('my/', MyFinanceStatView.as_view(), name='my-finance'),
    path('manual/', ManualFinanceEntryView.as_view(), name='manual-finance'),
    path('manual/list/', FinanceEntryListView.as_view(), name='finance-entry-list'),
    path('entries/create/', FinanceEntryCreateView.as_view(), name='finance-entry-create'),
    path('product/finance/', PartnerProductFinanceView.as_view(), name='partner-product-finance'),
    path('catalog/finance/', PartnerCatalogFinanceView.as_view(), name='partner-catalog-finance'),
    path('inventory/', PartnerInventoryView.as_view(), name='inventory-summary'),
    path('balance/', BalanceCalculatorView.as_view(), name='balance-calculator'),
    path('history/requests/', ProductRequestHistoryView.as_view(), name='request-history'),
    path('summary/', FinanceSummaryView.as_view(), name='finance-summary'),
    path('calendar/', CalendarStatisticsView.as_view(), name='calendar-statistics'),
    path('archives/', ArchivedDataView.as_view(), name='archived-data'),

    # Административные маршруты
    path('admin/damaged-report/', AdminDamagedGoodsReportView.as_view(), name='damaged-goods-report'),

    # API для моделей
    path('store-stats/', StoreFinanceStatListView.as_view(), name='store-finance-stats'),
    path('partner-statistics/', PartnerStatisticsView.as_view(), name='partner-statistics'),
    path('store-statistics/', StoreStatisticsView.as_view(), name='store-statistics'),
    path('admin-statistics/', AdminStatisticsView.as_view(), name='admin-statistics'),
]