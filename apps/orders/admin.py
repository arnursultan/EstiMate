from django.contrib import admin
from .models import ProductRequest


@admin.register(ProductRequest)
class ProductRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'product', 'user', 'quantity', 'bonus_quantity', 'damaged_quantity',
        'payment_method', 'status', 'for_store', 'store', 'total_price', 'created_at'
    )
    list_filter = ('status', 'payment_method', 'for_store')
    search_fields = ('product__name', 'user__email', 'store__name')
    readonly_fields = ('bonus_quantity', 'total_price', 'created_at')
