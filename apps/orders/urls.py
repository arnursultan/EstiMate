from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductRequestViewSet, RecordDamageView, RecordExpenseView, PayDebtView

router = DefaultRouter()
router.register(r'product-requests', ProductRequestViewSet, basename='product-request')

urlpatterns = [
    path('', include(router.urls)),
    # Пути для запросов товаров
    path('group-self-request/', ProductRequestViewSet.as_view({'post': 'group_self_request'}),
         name='group-self-request'),
    path('group-store-request/', ProductRequestViewSet.as_view({'post': 'group_store_request'}),
         name='group-store-request'),
    path('process-batch/', ProductRequestViewSet.as_view({'post': 'process_batch'}), name='process-batch'),

    # Пути для финансовых операций
    path('record-damage/', RecordDamageView.as_view(), name='record-damage'),
    path('record-expense/', RecordExpenseView.as_view(), name='record-expense'),
    path('pay-debt/', PayDebtView.as_view(), name='pay-debt'),
]