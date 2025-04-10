import django_filters
from .models import PartnerFinanceStat, StoreFinanceStat, FinanceEntry, CalendarStatistics, InventorySummary
from django_filters import rest_framework as filters
from apps.orders.models import ProductRequest

class DateRangeFilter(django_filters.FilterSet):
    from_date = django_filters.DateFilter(field_name="date", lookup_expr='gte')
    to_date = django_filters.DateFilter(field_name="date", lookup_expr='lte')


class PartnerFinanceStatFilter(DateRangeFilter):
    class Meta:
        model = PartnerFinanceStat
        fields = ['user', 'date']


class StoreFinanceStatFilter(DateRangeFilter):
    class Meta:
        model = StoreFinanceStat
        fields = ['store', 'date']


class FinanceEntryFilter(DateRangeFilter):
    class Meta:
        model = FinanceEntry
        fields = ['user', 'date', 'city', 'entry_type', 'partner_product']


class CalendarStatisticsFilter(DateRangeFilter):
    class Meta:
        model = CalendarStatistics
        fields = [
            'store', 'user', 'city', 'date',
            'has_sales', 'has_requests', 'has_expenses',
            'has_debt_payment', 'has_damages', 'has_returns'
        ]


class InventorySummaryFilter(DateRangeFilter):
    class Meta:
        model = InventorySummary
        fields = ['user', 'date']



class ProductRequestFilter(filters.FilterSet):
    created_at_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        model = ProductRequest
        fields = ['status', 'payment_method', 'store', 'created_at']

