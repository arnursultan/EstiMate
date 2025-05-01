from django.contrib import admin
from .models import City, Store, StoreDebt, StoreDebtPayment # Убрали StoreExpense


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('id','name',)
    search_fields = ('name',)


class StoreDebtInline(admin.TabularInline):
    model = StoreDebt
    extra = 0 # Не добавляем пустые по умолчанию
    readonly_fields = ('created_at', 'updated_at', 'is_paid')
    can_delete = False # Долги лучше не удалять из админки магазина напрямую


class StoreDebtPaymentInline(admin.TabularInline):
    model = StoreDebtPayment
    extra = 0 # Не добавляем пустые по умолчанию
    readonly_fields = ('payment_date',)
    can_delete = True


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = (
    'id','name', 'city', 'partner_display', 'status', 'is_active', 'is_deleted',
    'total_debt', 'total_paid_debt', 'remaining_debt', 'created_at'
    )
    list_filter = ('city', 'status', 'partner', 'created_at', 'is_active', 'is_deleted')
    search_fields = ('name', 'address', 'inn', 'phone', 'partner__email', 'partner__first_name')
    # Добавляем поля для быстрого редактирования в списке
    list_editable = ('status', 'is_active')
    readonly_fields = ('created_at', 'updated_at', 'total_debt', 'total_paid_debt', 'remaining_debt')
    # Убираем StoreExpenseInline
    inlines = [StoreDebtInline, StoreDebtPaymentInline]
    # Используем raw_id_fields для удобства выбора партнера и города
    raw_id_fields = ('partner', 'city')

    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'inn', 'phone', 'city', 'address')
        }),
        ('Финансы (Расчетные)', {
            'fields': ('total_debt', 'total_paid_debt', 'remaining_debt')
        }),
        ('Связи', {
            'fields': ('partner',)
        }),
        ('Статус и даты', {
            'fields': ('status', 'is_active', 'is_deleted', 'created_at', 'updated_at')
        }),
    )

    # Оставляем расчетные поля для отображения
    def total_debt(self, obj):
        return obj.total_debt
    total_debt.short_description = 'Общий долг'

    def total_paid_debt(self, obj):
        return obj.total_paid_debt
    total_paid_debt.short_description = 'Погашенный долг'

    def remaining_debt(self, obj):
        return obj.remaining_debt
    remaining_debt.short_description = 'Оставшийся долг'

    def partner_display(self, obj):
         if obj.partner:
              return f"{obj.partner.first_name} {obj.partner.last_name}"
         return "-"
    partner_display.short_description = 'Партнер'
    partner_display.admin_order_field = 'partner' # Добавляем сортировку

    # Убираем кастомный view статистики отсюда, его лучше делать через API
    # def get_urls(self): ...
    # def store_statistics_view(self, request, store_id): ...

    # Добавляем действие для мягкого удаления
    actions = ['make_soft_deleted', 'make_restored']

    @admin.action(description='Пометить выбранные магазины как удаленные')
    def make_soft_deleted(self, request, queryset):
        updated = queryset.update(is_deleted=True, is_active=False)
        self.message_user(request, f'{updated} магазинов были помечены как удаленные.')

    @admin.action(description='Восстановить выбранные магазины')
    def make_restored(self, request, queryset):
        updated = queryset.update(is_deleted=False, is_active=True)
        self.message_user(request, f'{updated} магазинов были восстановлены.')


@admin.register(StoreDebt)
class StoreDebtAdmin(admin.ModelAdmin):
    list_display = ('id', 'store', 'amount', 'is_paid', 'created_at', 'updated_at')
    list_filter = ('is_paid', 'created_at', 'store__city', 'store__partner')
    search_fields = ('store__name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('store',)


@admin.register(StoreDebtPayment)
class StoreDebtPaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'store', 'amount', 'payment_date')
    list_filter = ('payment_date', 'store__city', 'store__partner')
    search_fields = ('store__name', 'description')
    readonly_fields = ('payment_date',)
    raw_id_fields = ('store',)