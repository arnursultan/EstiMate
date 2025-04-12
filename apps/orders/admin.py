from django.contrib import admin
from .models import Order, OrderItem, DefectItem

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    readonly_fields = ('total_price', 'bonus_quantity', 'created_at')

class DefectItemInline(admin.TabularInline):
    model = DefectItem
    extra = 1
    readonly_fields = ('total_price', 'created_at')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'order_type', 'partner', 'store', 'status', 'is_group_order', 'total_price', 'created_at')
    list_filter = ('order_type', 'status', 'is_group_order', 'created_at')
    search_fields = ('partner__email', 'partner__first_name', 'partner__last_name', 'store__name')
    readonly_fields = ('created_at', 'updated_at', 'total_price', 'total_bonus_items')
    inlines = [OrderItemInline, DefectItemInline]

    fieldsets = (
        ('Основная информация', {
            'fields': ('created_by', 'order_type', 'status', 'is_group_order')
        }),
        ('Получатель', {
            'fields': ('partner', 'store')
        }),
        ('Дополнительно', {
            'fields': ('total_price', 'total_bonus_items', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'price', 'total_price', 'bonus_quantity', 'created_at')
    list_filter = ('created_at', 'order__status', 'order__order_type')
    search_fields = ('order__partner__email', 'order__store__name', 'product__name')
    readonly_fields = ('total_price', 'bonus_quantity', 'created_at')

    fieldsets = (
        ('Связи', {
            'fields': ('order', 'product')
        }),
        ('Заказ', {
            'fields': ('quantity', 'price', 'total_price', 'bonus_quantity')
        }),
        ('Дополнительно', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

@admin.register(DefectItem)
class DefectItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'total_price', 'created_at')
    list_filter = ('created_at', 'order__store')
    search_fields = ('order__store__name', 'product__name', 'description')
    readonly_fields = ('total_price', 'created_at')

    fieldsets = (
        ('Связи', {
            'fields': ('order', 'product')
        }),
        ('Детали', {
            'fields': ('quantity', 'description', 'total_price')
        }),
        ('Дополнительно', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )