from django.contrib import admin
from .models import City, Store, StoreDebt, StoreDebtPayment, StoreExpense


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


class StoreDebtInline(admin.TabularInline):
    model = StoreDebt
    extra = 1
    readonly_fields = ('created_at', 'updated_at')


class StoreDebtPaymentInline(admin.TabularInline):
    model = StoreDebtPayment
    extra = 1
    readonly_fields = ('payment_date',)


class StoreExpenseInline(admin.TabularInline):
    model = StoreExpense
    extra = 1
    readonly_fields = ('created_at',)


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = (
    'name', 'city', 'partner', 'status', 'total_debt', 'total_paid_debt', 'remaining_debt', 'expenses', 'created_at')
    list_filter = ('city', 'status', 'partner', 'created_at')
    search_fields = ('name', 'address', 'inn', 'phone')
    readonly_fields = ('created_at', 'updated_at', 'total_debt', 'total_paid_debt', 'remaining_debt')
    inlines = [StoreDebtInline, StoreDebtPaymentInline, StoreExpenseInline]

    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'inn', 'phone', 'city', 'address')
        }),
        ('Финансы', {
            'fields': ('expenses', 'total_debt', 'total_paid_debt', 'remaining_debt')
        }),
        ('Связи', {
            'fields': ('partner',)
        }),
        ('Статус', {
            'fields': ('status', 'created_at', 'updated_at')
        }),
    )

    def total_debt(self, obj):
        return obj.total_debt

    total_debt.short_description = 'Общий долг'

    def total_paid_debt(self, obj):
        return obj.total_paid_debt

    total_paid_debt.short_description = 'Погашенный долг'

    def remaining_debt(self, obj):
        return obj.remaining_debt

    remaining_debt.short_description = 'Оставшийся долг'


@admin.register(StoreDebt)
class StoreDebtAdmin(admin.ModelAdmin):
    list_display = ('store', 'amount', 'is_paid', 'created_at', 'updated_at')
    list_filter = ('is_paid', 'created_at', 'store__city')
    search_fields = ('store__name', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(StoreDebtPayment)
class StoreDebtPaymentAdmin(admin.ModelAdmin):
    list_display = ('store', 'amount', 'payment_date')
    list_filter = ('payment_date', 'store__city')
    search_fields = ('store__name', 'description')
    readonly_fields = ('payment_date',)


@admin.register(StoreExpense)
class StoreExpenseAdmin(admin.ModelAdmin):
    list_display = ('store', 'amount', 'expense_date', 'created_at')
    list_filter = ('expense_date', 'store__city')
    search_fields = ('store__name', 'description')
    readonly_fields = ('created_at',)