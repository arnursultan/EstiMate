from django.db import models
from apps.users.models import User
from apps.products.models import Product
from apps.stores.models import Store
from decimal import Decimal


class ProductRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'В ожидании'),
        ('approved', 'Подтвержден'),
        ('rejected', 'Отклонен'),
        ('received', 'Получен'),
    )

    PAYMENT_METHOD_CHOICES = (
        ('cash', 'Наличными'),
        ('debt', 'В долг'),
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='requests',
        verbose_name="Продукт"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='product_requests',
        verbose_name="Партнёр"
    )
    quantity = models.PositiveIntegerField(verbose_name="Запрошенное количество")
    bonus_quantity = models.PositiveIntegerField(default=0, verbose_name="Бонусное количество")
    damaged_quantity = models.PositiveIntegerField(default=0, verbose_name="Количество бракованных товаров")
    payment_method = models.CharField(
        max_length=10,
        choices=PAYMENT_METHOD_CHOICES,
        default='cash',
        verbose_name="Метод оплаты"
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Статус"
    )
    for_store = models.BooleanField(default=False, verbose_name="Для магазина")
    store = models.ForeignKey(
        Store,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='product_requests',
        verbose_name="Магазин"
    )
    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Общая сумма"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата запроса")

    previous_status = None  # для отслеживания изменения статуса

    class Meta:
        verbose_name = "Запрос на товар"
        verbose_name_plural = "Запросы на товары"
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        self.bonus_quantity = self.quantity // 21
        actual_qty = max(self.quantity - self.bonus_quantity - self.damaged_quantity, 0)
        self.total_price = actual_qty * self.product.price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} — {self.quantity} шт. от {self.user}"
