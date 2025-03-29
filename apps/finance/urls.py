from django.urls import path
from .views import (MyFinanceStatView, StoreFinanceView, ManualFinanceEntryView,
                    AdminFinanceStatView,CalendarStatisticsView, ArchivedDataView,
                    AdminDamagedGoodsReportView,BalanceCalculatorView)

app_name = 'finance'

# Обновить маршруты
urlpatterns = [
    path('my/', MyFinanceStatView.as_view(), name='my-finance'),
    path('stores/', StoreFinanceView.as_view(), name='store-finance'),
    path('manual/', ManualFinanceEntryView.as_view(), name='manual-finance'),
    path('admin/finance-stat/', AdminFinanceStatView.as_view(), name='admin-finance-stat'),
    path('calendar/', CalendarStatisticsView.as_view(), name='calendar-statistics'),
    path('archives/', ArchivedDataView.as_view(), name='archived-data'),
    path('balance/', BalanceCalculatorView.as_view(), name='balance-calculator'),
    path('admin/damaged-report/', AdminDamagedGoodsReportView.as_view(), name='damaged-goods-report'),
]
