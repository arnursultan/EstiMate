import django_filters
from .models import PartnerFinanceStat, StoreFinanceStat, FinanceEntry, CalendarStatistics


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
        fields = ['user', 'date', 'city']


class CalendarStatisticsFilter(DateRangeFilter):
    class Meta:
        model = CalendarStatistics
        fields = ['store', 'user', 'city', 'date', 'has_sales', 'has_requests', 'has_expenses', 'has_debt_payment']