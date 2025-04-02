from django.db import models
from django.core.exceptions import ValidationError
from apps.users.models import User
from apps.products.models import Product
from apps.stores.models import Store


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

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='requests')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_requests')
    quantity = models.PositiveIntegerField()
    bonus_quantity = models.PositiveIntegerField(default=0)
    damaged_quantity = models.PositiveIntegerField(default=0)
    is_bonus_marked = models.BooleanField(default=False)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, default='cash')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    for_store = models.BooleanField(default=False)
    store = models.ForeignKey(Store, on_delete=models.SET_NULL, null=True, blank=True, related_name='product_requests')
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    previous_status = None  # для отслеживания изменений статуса

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Запрос на товар"
        verbose_name_plural = "Запросы на товары"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.previous_status = self.status if self.pk else None

    def clean(self):
        """Валидация модели"""
        if self.for_store and not self.store:
            raise ValidationError("Для запроса на магазин необходимо указать магазин")

        if self.store and self.store.status != 'approved':
            raise ValidationError("Можно выбрать только подтвержденные магазины")

        if self.store and not self.store.is_active:
            raise ValidationError("Можно выбрать только активные магазины")

        if self.for_store and self.payment_method == 'debt' and not self.store:
            raise ValidationError("Для оплаты в долг необходимо выбрать магазин")

        if not self.for_store and self.payment_method == 'debt':
            raise ValidationError("Оплата в долг доступна только для магазинов")

    def save(self, *args, **kwargs):
        # Расчет бонусов
        if self.product.is_bonus_eligible:
            self.bonus_quantity = self.quantity // 21
        else:
            self.bonus_quantity = 0

        self.is_bonus_marked = self.bonus_quantity > 0

        # Расчет общей стоимости
        actual_qty = max(self.quantity - self.bonus_quantity - self.damaged_quantity, 0)
        self.total_price = actual_qty * self.product.price

        # Если запрос не для магазина и статус меняется на approved,
        # проверяем достаточно ли товара на складе
        if (not self.for_store and
                self.previous_status != 'approved' and
                self.status == 'approved' and
                self.product.quantity < self.quantity):
            raise ValidationError("Недостаточно товара на складе")

        super().save(*args, **kwargs)

        # Обновляем previous_status после сохранения
        self.previous_status = self.status

    def __str__(self):
        store_info = f" для {self.store}" if self.store else ""
        return f"{self.product.name} — {self.quantity} шт.{store_info} от {self.user}"

    def mark_as_received(self):
        """Отметить запрос как полученный"""
        if self.status != 'approved':
            raise ValidationError("Можно отметить как полученный только подтвержденный запрос")

        self.status = 'received'
        self.save()
        return True

    def report_damaged(self, damaged_quantity):
        """Отметить бракованные товары"""
        if damaged_quantity < 0:
            raise ValidationError("Количество бракованных товаров не может быть отрицательным")

        if damaged_quantity > self.quantity:
            raise ValidationError(
                f"Количество бракованных товаров ({damaged_quantity}) не может превышать общее количество ({self.quantity})")

        self.damaged_quantity = damaged_quantity
        self.save()
        return self.damaged_quantity