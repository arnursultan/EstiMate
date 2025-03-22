from django.contrib import admin
from .models import Product, ProductImage


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'quantity', 'is_bonus', 'is_active', 'created_at')
    list_filter = ('is_bonus', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'price', 'is_bonus')
        }),
        ('Характеристики', {
            'fields': ('weight', 'expiry_months', 'quantity')
        }),
        ('Изображение', {
            'fields': ('image',)
        }),
        ('Статус', {
            'fields': ('is_active',)
        }),
        ('Информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    inlines = [ProductImageInline]


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'order')
    list_filter = ('product',)