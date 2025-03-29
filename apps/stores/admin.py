from django.contrib import admin
from .models import City, Store, StoreDebt


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)

@admin.register(StoreDebt)
class StoreDebtAdmin(admin.ModelAdmin):
        # Удалите 'created_by' или замените его на корректное поле
    list_display = (
            'id', 'store', 'amount', 'request', 'created_at', 'is_paid'  # Удалено 'created_by'
    )
    list_filter = ('is_paid', 'created_at')
    search_fields = ('store__name', 'request__id')
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


