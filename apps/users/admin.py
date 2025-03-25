from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("id", "email", "phone", "role", "is_active", "is_staff", "status")
    list_filter = ("role", "is_active", "is_staff","status")
    search_fields = ("email", "phone")
    ordering = ("email",)
    readonly_fields = ("last_login",)

    fieldsets = (
        ("Основная информация", {"fields": ("photo","email", "phone", "first_name", "last_name", "role")}),
        ("Безопасность", {"fields": ("password",)}),
        ("Статус", {"fields": ("is_active", "is_staff", "is_superuser", "last_login","status")}),
    )

    add_fieldsets = (
        (
            "Создание нового пользователя",
            {
                "classes": ("wide",),
                "fields": ("email", "phone", "password1", "password2", "role", "is_active"),
            },
        ),
    )

