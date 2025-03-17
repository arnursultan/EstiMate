from django.contrib import admin
from .models import Store

@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "inn", "city", "debt", "payment", "status", "owner", "created_at")
    search_fields = ("name", "inn", "owner__email")
    list_filter = ("city", "status")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
    list_editable = ("status", "debt", "payment")

    fieldsets = (
        ("Основная информация", {
            "fields": ("name", "inn", "city", "owner", "status")
        }),
        ("Финансовые данные", {
            "fields": ("debt", "payment"),
        }),
        ("Дополнительно", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
