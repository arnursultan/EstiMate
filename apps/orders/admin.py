from django.contrib import admin
from .models import ProductRequest


@admin.register(ProductRequest)
class ProductRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'product', 'user', 'quantity', 'bonus_quantity', 'damaged_quantity',
        'payment_method', 'status', 'for_store', 'store', 'total_price', 'created_at'
    )
    list_filter = ('status', 'payment_method', 'for_store', 'created_at')
    search_fields = ('product__name', 'user__email', 'store__name')
    readonly_fields = ('bonus_quantity', 'total_price', 'created_at', 'is_bonus_marked')

    fieldsets = (
        ('Основная информация', {
            'fields': ('product', 'user', 'quantity', 'status')
        }),
        ('Магазин', {
            'fields': ('for_store', 'store', 'payment_method')
        }),
        ('Расчеты', {
            'fields': ('bonus_quantity', 'damaged_quantity', 'total_price', 'is_bonus_marked')
        }),
        ('Даты', {
            'fields': ('created_at',)
        }),
    )

    def has_delete_permission(self, request, obj=None):
        # Запрещаем удаление запросов со статусом approved или received
        if obj and obj.status in ['approved', 'received']:
            return False
        return True