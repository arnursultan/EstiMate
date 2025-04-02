from django.db import models
from django.core.exceptions import ValidationError


class Product(models.Model):
    name = models.CharField(max_length=255, verbose_name="Название продукта")
    description = models.TextField(blank=True, verbose_name="Описание продукта")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Цена"
    )
    image = models.ImageField(
        upload_to='products/photos/',
        blank=True,
        null=True,
        verbose_name="Изображение"
    )
    quantity = models.PositiveIntegerField(default=0, verbose_name="Количество на складе")
    is_bonus_eligible = models.BooleanField(default=True, verbose_name="Участвует в бонусной программе")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Продукт"
        verbose_name_plural = "Продукты"
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def add_quantity(self, amount):
        """Добавить количество товара на склад"""
        if amount <= 0:
            raise ValidationError("Количество добавляемого товара должно быть положительным")

        self.quantity += amount
        self.save()
        return self.quantity

    def reduce_quantity(self, amount):
        """Уменьшить количество товара на складе"""
        if amount <= 0:
            raise ValidationError("Количество уменьшаемого товара должно быть положительным")

        if self.quantity < amount:
            raise ValidationError("Недостаточно товара на складе")

        self.quantity -= amount
        self.save()
        return self.quantity

    def calculate_bonus(self, quantity_requested):
        """Расчет бонусов для товара"""
        if not self.is_bonus_eligible:
            return 0

        return quantity_requested // 21

    def calculate_total_price(self, quantity, bonus_quantity=None):
        """Расчет общей стоимости с учетом бонусов"""
        if bonus_quantity is None:
            bonus_quantity = self.calculate_bonus(quantity)

        charged_quantity = quantity - bonus_quantity
        return charged_quantity * self.price