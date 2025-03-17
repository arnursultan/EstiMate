from django.contrib import admin
from .models import OrderRequest

@admin.register(OrderRequest)
class OrderRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "store_name", "partner", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("store_name", "inn", "partner__email")
    ordering = ("-created_at",)
    actions = ["approve_selected"]

    def approve_selected(self, request, queryset):
        for order in queryset:
            order.approve()

    approve_selected.short_description = "Подтвердить выбранные заявки"
