# apps/finance/admin.py
from django.contrib import admin
from .models import ManualFinanceEntry, FinanceStatistics, PartnerExpense
from django.utils.html import format_html

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


@admin.register(PartnerExpense)
class PartnerExpenseAdmin(admin.ModelAdmin):
    list_display = ('id', 'partner_link', 'amount', 'expense_date', 'short_description', 'created_at')
    list_filter = ('expense_date', 'partner__email') # Фильтр по дате и email партнера
    search_fields = ('description', 'partner__first_name', 'partner__last_name', 'partner__email') # Поиск
    date_hierarchy = 'expense_date' # Иерархия по дате расхода
    list_select_related = ('partner',) # Оптимизация запроса
    raw_id_fields = ('partner',) # Удобный выбор партнера

    fieldsets = (
        (None, {
            'fields': ('partner', 'amount', 'expense_date', 'description')
        }),
        ('Системная информация', {
            'fields': ('created_at',),
            'classes': ('collapse',) # Скрыть по умолчанию
        }),
    )
    readonly_fields = ('created_at',)

    @admin.display(description='Партнер', ordering='partner__last_name')
    def partner_link(self, obj):
        """Ссылка на страницу партнера в админке"""
        if obj.partner:
            from django.urls import reverse
            link = reverse("admin:users_user_change", args=[obj.partner.id]) # Убедись, что имя модели правильное (users_user)
            return format_html('<a href="{}">{} {}</a>', link, obj.partner.first_name, obj.partner.last_name)
        return "-"

    @admin.display(description='Описание')
    def short_description(self, obj):
        """Короткое описание"""
        if obj.description:
            return obj.description[:50] + ('...' if len(obj.description) > 50 else '')
        return "-"