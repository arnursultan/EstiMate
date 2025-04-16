from django.contrib import admin
from .models import Product, PartnerInventory


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'price', 'quantity', 'is_bonus', 'is_active', 'created_at')
    list_filter = ('is_bonus', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'description', 'price', 'quantity', 'image', 'is_bonus', 'is_active')
        }),
        ('Дополнительная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PartnerInventory)
class PartnerInventoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'partner', 'product', 'quantity', 'created_at')
    list_filter = ('partner', 'created_at')
    search_fields = ('partner__email', 'product__name')
    readonly_fields = ('created_at', 'updated_at')