from django.contrib import admin
from .models import (PartnerFinanceStat, StoreFinanceStat, FinanceEntry,
                     ArchivedDailySummary, CalendarStatistics)


@admin.register(PartnerFinanceStat)
class PartnerFinanceStatAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'total_approved_cash', 'total_damaged_loss', 'total_profit')
    list_filter = ('date', 'user')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    date_hierarchy = 'date'


@admin.register(StoreFinanceStat)
class StoreFinanceStatAdmin(admin.ModelAdmin):
    list_display = ('store', 'date', 'total_approved', 'total_damaged', 'total_debt')
    list_filter = ('date', 'store__city')
    search_fields = ('store__name', 'store__inn')
    date_hierarchy = 'date'


@admin.register(FinanceEntry)
class FinanceEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'city', 'income', 'expense', 'profit', 'note')
    list_filter = ('date', 'user', 'city')
    search_fields = ('user__email', 'note', 'city__name')
    date_hierarchy = 'date'


@admin.register(CalendarStatistics)
class CalendarStatisticsAdmin(admin.ModelAdmin):
    list_display = ('date', 'user', 'store', 'city', 'has_sales', 'has_requests', 'has_expenses', 'has_debt_payment')
    list_filter = ('date', 'has_sales', 'has_requests', 'has_expenses', 'has_debt_payment')
    search_fields = ('user__email', 'store__name', 'city__name')
    date_hierarchy = 'date'


@admin.register(ArchivedDailySummary)
class ArchivedDailySummaryAdmin(admin.ModelAdmin):
    list_display = ('date', 'user', 'total_requests', 'total_sales', 'total_expenses', 'total_profit')
    list_filter = ('date',)
    search_fields = ('user__email',)
    date_hierarchy = 'date'
    readonly_fields = ('data',)  # JSON-данные лучше сделать только для чтения

    def has_add_permission(self, request):
        # Запрещаем добавление, т.к. эти данные должны создаваться только автоматически
        return False

    def has_delete_permission(self, request, obj=None):
        # Запрещаем удаление архивных данных
        return False