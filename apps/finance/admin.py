from django.contrib import admin
from .models import (
    PartnerFinanceStat, StoreFinanceStat, FinanceEntry,
    CalendarStatistics, ArchivedDailySummary
)
from django.utils.html import format_html
from django.db.models import Sum


class PartnerFinanceStatAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'total_requested_quantity', 'total_sold_quantity',
                    'total_damaged_quantity', 'total_bonus_quantity', 'total_remaining_quantity',
                    ]
    list_filter = ['date', 'user']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    date_hierarchy = 'date'



class StoreFinanceStatAdmin(admin.ModelAdmin):
    list_display = ['store', 'date', 'total_received_quantity', 'total_damaged_quantity',
                    'total_bonus_quantity', 'get_total_debt', 'get_total_paid_debt']
    list_filter = ['date', 'store', 'store__city']
    search_fields = ['store__name']
    date_hierarchy = 'date'

    def get_total_debt(self, obj):
        # Отображаем долг с цветовым форматированием
        debt = float(obj.total_debt or 0)
        color = 'red' if debt > 0 else 'green'
        return format_html('<span style="color: {};">{:.2f}</span>', color, debt)

    get_total_debt.short_description = "Долг"

    def get_total_paid_debt(self, obj):
        # Отображаем оплаченный долг
        paid = float(obj.total_paid_debt or 0)
        return format_html('<span style="color: green;">{:.2f}</span>', paid)

    get_total_paid_debt.short_description = "Оплачено"


class FinanceEntryAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'entry_type', 'quantity', 'amount', 'note']
    list_filter = ['date', 'entry_type', 'user']
    search_fields = ['user__email', 'note']
    date_hierarchy = 'date'


class CalendarStatisticsAdmin(admin.ModelAdmin):
    list_display = ['date', 'user', 'has_sales', 'has_requests', 'has_expenses', 'has_debt_payment']
    list_filter = ['date', 'user', 'has_sales', 'has_requests', 'has_expenses', 'has_debt_payment']
    date_hierarchy = 'date'


class ArchivedDailySummaryAdmin(admin.ModelAdmin):
    list_display = ['date', 'user', 'total_requests', 'get_total_sales', 'get_total_expenses', 'get_total_profit']
    list_filter = ['date', 'user']
    search_fields = ['user__email']
    date_hierarchy = 'date'

    def get_total_sales(self, obj):
        # Форматируем продажи
        return f"{float(obj.total_sales):.2f}"

    get_total_sales.short_description = "Продажи"

    def get_total_expenses(self, obj):
        # Форматируем расходы
        return f"{float(obj.total_expenses):.2f}"

    get_total_expenses.short_description = "Расходы"

    def get_total_profit(self, obj):
        # Форматируем прибыль с цветом
        profit = float(obj.total_profit)
        color = 'green' if profit >= 0 else 'red'
        return format_html('<span style="color: {};">{:.2f}</span>', color, profit)

    get_total_profit.short_description = "Прибыль"


# Регистрация моделей с классами админки
admin.site.register(PartnerFinanceStat, PartnerFinanceStatAdmin)
admin.site.register(StoreFinanceStat, StoreFinanceStatAdmin)
admin.site.register(FinanceEntry, FinanceEntryAdmin)
admin.site.register(CalendarStatistics, CalendarStatisticsAdmin)
admin.site.register(ArchivedDailySummary, ArchivedDailySummaryAdmin)