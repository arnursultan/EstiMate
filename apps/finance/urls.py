from django.urls import path
from .views import MyFinanceStatView, StoreFinanceView, ManualFinanceEntryView

urlpatterns = [
    path('my/', MyFinanceStatView.as_view(), name='my-finance'),
    path('stores/', StoreFinanceView.as_view(), name='store-finance'),
    path('manual/', ManualFinanceEntryView.as_view(), name='manual-finance'),
]
