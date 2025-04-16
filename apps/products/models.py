from django.db import models
from django.core.validators import MinValueValidator
from apps.users.models import User
from decimal import Decimal


class Product(models.Model):
    """Модель товара"""
    name = models.CharField(max_length=100, verbose_name="Название товара")
    description = models.TextField(verbose_name="Описание товара")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name="Цена"
    )
    quantity = models.PositiveIntegerField(default=0, verbose_name="Количество на складе")
    image = models.ImageField(upload_to='products/', null=True, blank=True, verbose_name="Изображение товара")
    is_bonus = models.BooleanField(default=False, verbose_name="Участвует в бонусной программе")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.price} сом"


class PartnerInventory(models.Model):
    """Модель инвентаря партнера"""
    partner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="inventory",
        verbose_name="Партнер"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="partner_inventories",
        verbose_name="Товар"
    )
    quantity = models.PositiveIntegerField(default=0, verbose_name="Количество")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Инвентарь партнера"
        verbose_name_plural = "Инвентарь партнеров"
        unique_together = ['partner', 'product']

    def __str__(self):
        return f"{self.partner.email} - {self.product.name} ({self.quantity})"