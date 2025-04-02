from django.contrib import admin
from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'price', 'quantity', 'is_bonus_eligible', 'created_at')
    list_filter = ('is_bonus_eligible', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'description', 'price', 'image')
        }),
        ('Настройки инвентаря', {
            'fields': ('quantity', 'is_bonus_eligible')
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