from django.contrib import admin
from .models import Product, PartnerProduct


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'price', 'quantity', 'is_bonus_eligible', 'is_active', 'created_at')
    list_filter = ('is_bonus_eligible', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'description', 'price', 'image')
        }),
        ('Настройки инвентаря', {
            'fields': ('quantity', 'is_bonus_eligible', 'is_active')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def has_delete_permission(self, request, obj=None):
        # Запрещаем удаление продуктов, чтобы сохранить историю
        # Вместо этого можно использовать деактивацию
        if obj and obj.quantity > 0:
            return False
        return True


@admin.register(PartnerProduct)
class PartnerProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'partner', 'product', 'quantity', 'sold_quantity', 'damaged_quantity', 'remaining_quantity', 'price')
    list_filter = ('created_at', 'partner')
    search_fields = ('product__name', 'partner__email')
    readonly_fields = ('created_at', 'updated_at', 'remaining_quantity')

    fieldsets = (
        ('Основная информация', {
            'fields': ('partner', 'product', 'price')
        }),
        ('Количество', {
            'fields': ('quantity', 'sold_quantity', 'damaged_quantity', 'bonus_quantity', 'returned_quantity', 'remaining_quantity')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )