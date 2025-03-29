from django.contrib import admin
from .models import (PartnerFinanceStat, StoreFinanceStat, FinanceEntry,
                     ArchivedDailySummary, CalendarStatistics)


@admin.register(PartnerFinanceStat)
class PartnerFinanceStatAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'total_approved_cash', 'total_damaged_loss', 'total_profit')


@admin.register(StoreFinanceStat)
class StoreFinanceStatAdmin(admin.ModelAdmin):
    list_display = ('store', 'date', 'total_approved', 'total_damaged', 'total_debt')


@admin.register(FinanceEntry)
class FinanceEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'city', 'income', 'expense', 'profit', 'note')


# Обновить регистрацию моделей
@admin.register(CalendarStatistics)
class CalendarStatisticsAdmin(admin.ModelAdmin):
    list_display = ('date', 'user', 'store', 'city', 'has_sales', 'has_requests', 'has_expenses')
    list_filter = ('date', 'has_sales', 'has_requests', 'has_expenses')
    search_fields = ('user__email', 'store__name', 'city__name')

@admin.register(ArchivedDailySummary)
class ArchivedDailySummaryAdmin(admin.ModelAdmin):
    list_display = ('date', 'user', 'total_requests', 'total_sales', 'total_expenses', 'total_profit')
    list_filter = ('date',)
    search_fields = ('user__email',)