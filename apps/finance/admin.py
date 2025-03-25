from django.contrib import admin
from .models import PartnerFinanceStat, StoreFinanceStat, FinanceEntry


@admin.register(PartnerFinanceStat)
class PartnerFinanceStatAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'total_approved_cash', 'total_damaged_loss', 'total_profit')


@admin.register(StoreFinanceStat)
class StoreFinanceStatAdmin(admin.ModelAdmin):
    list_display = ('store', 'date', 'total_approved', 'total_damaged', 'total_debt')


@admin.register(FinanceEntry)
class FinanceEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'city', 'income', 'expense', 'profit', 'note')
