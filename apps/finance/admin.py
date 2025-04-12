from django.contrib import admin
from .models import (
    PartnerFinanceEntry,
    StoreFinanceEntry,
    DailyStatistics,
    ProductDailyStatistics
)


class ProductDailyStatisticsInline(admin.TabularInline):
    model = ProductDailyStatistics
    extra = 0
    readonly_fields = (
        'product_id', 'product_name', 'requested_quantity', 'sold_quantity',
        'bonus_quantity', 'defect_quantity', 'remaining_quantity', 'income_amount'
    )
    can_delete = False
    show_change_link = False


@admin.register(DailyStatistics)
class DailyStatisticsAdmin(admin.ModelAdmin):
    list_display = (
        'date', 'get_partner_or_store', 'total_income', 'total_expense',
        'total_balance', 'total_defect_items', 'total_bonus_items'
    )
    list_filter = ('date', 'partner', 'store__city')
    search_fields = ('partner__first_name', 'partner__last_name', 'store__name')
    date_hierarchy = 'date'
    readonly_fields = (
        'date', 'partner', 'store', 'total_income', 'total_expense',
        'total_debt', 'total_debt_paid', 'total_bonus_amount', 'total_bonus_items',
        'total_defect_items', 'total_remaining_items', 'total_balance',
        'created_at', 'updated_at'
    )
    inlines = [ProductDailyStatisticsInline]

    def get_partner_or_store(self, obj):
        if obj.partner:
            return f"{obj.partner.first_name} {obj.partner.last_name} (Партнер)"
        elif obj.store:
            return f"{obj.store.name} (Магазин)"
        return "Общая статистика"

    get_partner_or_store.short_description = "Партнер/Магазин"


@admin.register(PartnerFinanceEntry)
class PartnerFinanceEntryAdmin(admin.ModelAdmin):
    list_display = ('partner', 'entry_type', 'amount', 'date', 'created_at')
    list_filter = ('entry_type', 'date', 'partner')
    search_fields = ('partner__first_name', 'partner__last_name', 'description')
    date_hierarchy = 'date'
    raw_id_fields = ('partner',)

    fieldsets = (
        ('Основная информация', {
            'fields': ('partner', 'entry_type', 'amount', 'date')
        }),
        ('Дополнительно', {
            'fields': ('description', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(StoreFinanceEntry)
class StoreFinanceEntryAdmin(admin.ModelAdmin):
    list_display = ('store', 'entry_type', 'amount', 'date', 'created_at')
    list_filter = ('entry_type', 'date', 'store__city')
    search_fields = ('store__name', 'description')
    date_hierarchy = 'date'
    raw_id_fields = ('store',)

    fieldsets = (
        ('Основная информация', {
            'fields': ('store', 'entry_type', 'amount', 'date')
        }),
        ('Дополнительно', {
            'fields': ('description', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at')