from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("id", "email", "phone", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "phone", "login")
    ordering = ("email",)
    readonly_fields = ("last_login",)

    fieldsets = (
        ("Основная информация", {"fields": ("email", "login", "phone", "full_name", "role")}),
        ("Безопасность", {"fields": ("password",)}),
        ("Статус", {"fields": ("is_active", "is_staff", "is_superuser", "last_login")}),
        ("Группы и разрешения", {"fields": ("groups", "user_permissions")}),
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

    filter_horizontal = ("groups", "user_permissions")
