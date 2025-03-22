from django.contrib import admin
from .models import Store,Application

@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "inn", "city", "debt", "payment_total", "status", "owner", "created_at")
    search_fields = ("name", "inn", "owner__email")
    list_filter = ("city", "status")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
    list_editable = ("status", "debt", "payment_total")  # Используем payment_total вместо payment

    fieldsets = (
        ("Основная информация", {
            "fields": ("name", "inn", "city", "owner", "status")
        }),
        ("Финансовые данные", {
            "fields": ("debt", "payment_total"),
        }),
        ("Дополнительно", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "inn", "city", "status", "created_at")
    search_fields = ("full_name", "inn")
    list_filter = ("status", "city")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)

    fieldsets = (
        ("Основная информация", {
            "fields": ("full_name", "phone_number", "inn", "city", "address", "title")
        }),
        ("Статус заявки", {
            "fields": ("status",),
        }),
        ("Дополнительно", {
            "fields": ("created_at",),
            "classes": ("collapse",),
        }),
    )