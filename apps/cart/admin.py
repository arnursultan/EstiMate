from django.contrib import admin
from .models import CartItem


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'cart_type', 'get_product_name', 'store', 'quantity', 'created_at')
    list_filter = ('cart_type', 'created_at')
    search_fields = ('user__email', 'product__name', 'partner_product__product__name', 'store__name')

    def get_product_name(self, obj):
        if obj.cart_type == 'SELF' and obj.product:
            return obj.product.name
        elif obj.cart_type == 'STORE' and obj.partner_product:
            return obj.partner_product.product.name
        return None

    get_product_name.short_description = 'Товар'