from django.contrib import admin
from .models import City, Store, StoreDebt


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'inn', 'city', 'status', 'is_active', 'creator', 'created_at')
    search_fields = ('name', 'inn', 'address', 'phone')
    list_filter = ('status', 'is_active', 'city', 'created_at')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(StoreDebt)
class StoreDebtAdmin(admin.ModelAdmin):
    list_display = ('id', 'store', 'amount', 'request', 'created_by', 'created_at', 'is_paid', 'paid_at')
    list_filter = ('is_paid', 'created_at', 'store__city')
    search_fields = ('store__name', 'store__inn', 'request__id')
    readonly_fields = ('created_at', 'paid_at')

    def has_delete_permission(self, request, obj=None):
        return False