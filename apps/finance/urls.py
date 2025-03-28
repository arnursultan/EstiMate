from django.urls import path
from .views import MyFinanceStatView, StoreFinanceView, ManualFinanceEntryView, AdminFinanceStatView

app_name = 'finance'

urlpatterns = [
    path('my/', MyFinanceStatView.as_view(), name='my-finance'),
    path('stores/', StoreFinanceView.as_view(), name='store-finance'),
    path('manual/', ManualFinanceEntryView.as_view(), name='manual-finance'),
    path('admin/finance-stat/',AdminFinanceStatView.as_view(), name='admin-finance-stat'),
]
