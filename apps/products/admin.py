from django.contrib import admin
from django.utils.html import format_html
from .models import ProductCategory, Product, ProductImage


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)
    ordering = ("id",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "price", "stock", "bonus", "status", "owner", "created_at")
    list_filter = ("category", "status", "bonus")
    search_fields = ("name", "category__name", "owner__email")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at", "bonus")
    list_editable = ("price", "stock", "status")
    fieldsets = (
        ("Основная информация", {
            "fields": ("name", "description", "category", "price", "currency", "status", "stock", "owner")
        }),
        ("Дополнительно", {
            "fields": ("created_at", "updated_at", "bonus"),
            "classes": ("collapse",),
        }),
    )
    list_per_page = 20
    autocomplete_fields = ("category", "owner")


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "is_main", "image_preview")
    list_filter = ("is_main", "product__category")
    search_fields = ("product__name",)
    ordering = ("-id",)

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image.url)
        return "Нет изображения"

    image_preview.short_description = "Превью"
