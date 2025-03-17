from django.db import models
from django.conf import settings
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile

class ProductCategory(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="Название категории")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Категорию"
        verbose_name_plural = "Категории"


class Product(models.Model):
    STATUS_CHOICES = [
        ("available", "В наличии"),
        ("out_of_stock", "Нет в наличии"),
    ]

    name = models.CharField(max_length=255, verbose_name="Название")
    description = models.TextField(max_length=255, blank=True, null=True, verbose_name="Описание")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена")
    currency = models.CharField(max_length=10, default="USD", verbose_name="Валюта")
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Категория")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="available", verbose_name="Статус")
    stock = models.PositiveIntegerField(default=0, verbose_name="Остаток на складе")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    bonus = models.BooleanField(default=False, verbose_name="Бонусный товар")

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Владелец")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Продукт"
        verbose_name_plural = "Продукты"


class ProductImage(models.Model):
    product = models.ForeignKey("Product", on_delete=models.CASCADE, related_name="images", verbose_name="Продукт")
    image = models.ImageField(upload_to="products/images/", verbose_name="Фото")
    is_main = models.BooleanField(default=False, verbose_name="Основное фото")

    def save(self, *args, **kwargs):
        img = Image.open(self.image)

        if img.format == "PNG" and not img.info.get("transparency"):
            img = img.convert("RGB")

        max_width = 1280
        if img.width > max_width:
            new_height = int((max_width / img.width) * img.height)
            img = img.resize((max_width, new_height), Image.LANCZOS)

        img_io = BytesIO()
        img.save(img_io, format="JPEG", quality=70, optimize=True)

        self.image = ContentFile(img_io.getvalue(), name=self.image.name)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Фото {self.product.name}"

    class Meta:
        verbose_name = "Фото продукта"
        verbose_name_plural = "Фото продуктов"