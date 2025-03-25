from django.contrib import admin
from .models import City, Store, StoreDebt


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'inn', 'city', 'phone', 'status', 'is_active', 'created_at')
    list_filter = ('city', 'status', 'is_active')
    search_fields = ('name', 'inn', 'address', 'phone')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['approve_stores', 'reject_stores', 'activate_stores', 'deactivate_stores']

    def approve_stores(self, request, queryset):
        updated = queryset.filter(status='pending').update(status='approved')
        self.message_user(request, f'Подтверждено {updated} магазинов')

    approve_stores.short_description = 'Подтвердить выбранные магазины'

    def reject_stores(self, request, queryset):
        updated = queryset.filter(status='pending').update(status='rejected')
        self.message_user(request, f'Отклонено {updated} магазинов')

    reject_stores.short_description = 'Отклонить выбранные магазины'

    def activate_stores(self, request, queryset):
        updated = queryset.filter(is_active=False).update(is_active=True)
        self.message_user(request, f'Активировано {updated} магазинов')

    activate_stores.short_description = 'Активировать выбранные магазины'

    def deactivate_stores(self, request, queryset):
        updated = queryset.filter(is_active=True).update(is_active=False)
        self.message_user(request, f'Деактивировано {updated} магазинов')

    deactivate_stores.short_description = 'Деактивировать выбранные магазины'

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StoreDebt)
class StoreDebtAdmin(admin.ModelAdmin):
    list_display = ('id', 'store', 'amount', 'is_paid', 'created_at', 'paid_at', 'created_by')
    list_filter = ('is_paid', 'created_at', 'store')
    search_fields = ('store__name', 'description')
    readonly_fields = ('created_at', 'paid_at')
    actions = ['mark_as_paid']

    def mark_as_paid(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(is_paid=False).update(is_paid=True, paid_at=timezone.now())
        self.message_user(request, f'Отмечено как оплаченные {updated} долгов')

    mark_as_paid.short_description = 'Отметить выбранные долги как оплаченные'