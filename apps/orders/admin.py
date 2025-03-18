from django.contrib import admin
from .models import OrderRequest

@admin.register(OrderRequest)
class OrderRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "store_name", "inn", "city", "status", "created_at")
    list_filter = ("status", "city")
    search_fields = ("store_name", "inn", "partner__email")

    def save_model(self, request, obj, form, change):
        if obj.status == "approved" and "status" in form.changed_data:
            obj.approve()
        super().save_model(request, obj, form, change)
