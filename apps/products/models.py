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
    is_active = models.BooleanField(default=True, verbose_name="Активен")

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


class PartnerProduct(models.Model):
    partner = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='partner_products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='partner_instances')
    quantity = models.PositiveIntegerField(default=0, verbose_name="Общее количество")
    sold_quantity = models.PositiveIntegerField(default=0, verbose_name="Продано")
    damaged_quantity = models.PositiveIntegerField(default=0, verbose_name="Брак")
    bonus_quantity = models.PositiveIntegerField(default=0, verbose_name="Бонус")
    returned_quantity = models.PositiveIntegerField(default=0, verbose_name="Возвращено")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Товар партнера"
        verbose_name_plural = "Товары партнеров"
        unique_together = ['partner', 'product']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product.name} ({self.partner.email})"

    @property
    def remaining_quantity(self):
        """
        Расчет оставшегося количества (бонус не учитывается в остатке)
        """
        return max(0, self.quantity - self.sold_quantity - self.damaged_quantity)

    def update_quantity(self, amount, operation='add'):
        """
        Обновление количества товара
        operation: 'add' или 'subtract'
        """
        if operation == 'add':
            self.quantity += amount
        elif operation == 'subtract':
            if amount > self.remaining_quantity:
                raise ValidationError(f"Недостаточно товара. Доступно: {self.remaining_quantity}")
            self.quantity -= amount
        self.save()
        return self.quantity

    def record_sale(self, amount):
        """Записать продажу"""
        if amount > self.remaining_quantity:
            raise ValidationError(f"Недостаточно товара для продажи. Доступно: {self.remaining_quantity}")
        self.sold_quantity += amount
        self.save()
        return self.sold_quantity

    # Модифицируем apps/products/models.py - метод record_damage в PartnerProduct

    def record_damage(self, amount):
        """Записать брак (не влияет на остаток)"""
        if amount < 0:
            raise ValidationError("Количество бракованных товаров не может быть отрицательным")

        self.damaged_quantity += amount
        self.save()
        return self.damaged_quantity

    def record_return(self, amount):
        """Записать возврат"""
        if amount > self.sold_quantity:
            raise ValidationError(f"Возврат не может превышать проданное количество ({self.sold_quantity})")
        self.returned_quantity += amount
        self.sold_quantity -= amount
        self.save()
        return self.returned_quantity
