# apps/finance/admin.py
from django.contrib import admin
from .models import ManualFinanceEntry, FinanceStatistics


@admin.register(ManualFinanceEntry)
class ManualFinanceEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'entry_type', 'amount', 'date', 'created_at')
    list_filter = ('entry_type', 'date', 'user__role')
    search_fields = ('description', 'user__email', 'user__first_name', 'user__last_name')
    date_hierarchy = 'date'


@admin.register(FinanceStatistics)
class FinanceStatisticsAdmin(admin.ModelAdmin):
    list_display = ('date', 'total_orders', 'total_sales', 'total_expenses', 'created_at')
    list_filter = ('date',)
    date_hierarchy = 'date'