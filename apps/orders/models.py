import uuid
from django.db import models
from django.core.exceptions import ValidationError
from apps.users.models import User
from apps.products.models import Product
from apps.stores.models import Store
from apps.products.models import PartnerProduct


class ProductRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'В ожидании'),
        ('approved', 'Подтвержден'),
        ('rejected', 'Отклонен'),
        ('received', 'Получен'),
    )

    REQUEST_TYPE_CHOICES = (
        ('SELF', 'Для себя'),
        ('STORE', 'Для магазина'),
    )

    PAYMENT_METHOD_CHOICES = (
        ('debt', 'В долг'),  # Только долг в новом ТЗ, наличные удалены
    )

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='requests')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_requests')
    quantity = models.PositiveIntegerField()
    bonus_quantity = models.PositiveIntegerField(default=0)
    damaged_quantity = models.PositiveIntegerField(default=0)
    is_bonus_marked = models.BooleanField(default=False)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, default='debt')
    request_type = models.CharField(max_length=5, choices=REQUEST_TYPE_CHOICES, default='SELF')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    store = models.ForeignKey(Store, on_delete=models.SET_NULL, null=True, blank=True, related_name='product_requests')
    # Добавляем связь с товаром партнера для STORE-запросов
    partner_product = models.ForeignKey(
        PartnerProduct,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='store_requests'
    )
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    # Добавляем поле для групповых заявок
    batch_id = models.UUIDField(
        null=True,
        blank=True,
        verbose_name="ID групповой заявки",
        db_index=True,  # Добавляем индекс для ускорения поиска
        help_text="Уникальный идентификатор для связывания запросов в группу"
    )

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
        # Для SELF-запросов не нужен магазин и partner_product
        if self.request_type == 'SELF':
            if self.store:
                raise ValidationError("Для запроса 'для себя' не нужно указывать магазин")
            if self.partner_product:
                raise ValidationError("Для запроса 'для себя' не нужно указывать товар из личного каталога")

        # Для STORE-запросов нужен магазин и partner_product
        if self.request_type == 'STORE':
            if not self.store:
                raise ValidationError("Для запроса в магазин необходимо указать магазин")
            if not self.partner_product:
                raise ValidationError("Для запроса в магазин необходимо указать товар из личного каталога")

            # Проверяем, что магазин подтвержден и активен
            if self.store and self.store.status != 'approved':
                raise ValidationError("Можно выбрать только подтвержденные магазины")
            if self.store and not self.store.is_active:
                raise ValidationError("Можно выбрать только активные магазины")

    def save(self, *args, **kwargs):
        is_new = self.pk is None  # Проверяем, создаем ли новый объект

        # Расчет бонусов для запросов
        if self.request_type == 'SELF' and self.product and self.product.is_bonus_eligible:
            self.bonus_quantity = self.product.calculate_bonus(self.quantity)
        elif self.request_type == 'STORE' and self.partner_product and self.partner_product.product.is_bonus_eligible:
            self.bonus_quantity = self.partner_product.product.calculate_bonus(self.quantity)
        else:
            self.bonus_quantity = 0

        self.is_bonus_marked = self.bonus_quantity > 0

        # Расчет общей стоимости (без учета бонусов и брака)
        actual_qty = max(self.quantity - self.bonus_quantity - self.damaged_quantity, 0)

        if self.request_type == 'SELF' and self.product:
            self.total_price = actual_qty * self.product.price
        elif self.request_type == 'STORE' and self.partner_product:
            self.total_price = actual_qty * self.partner_product.price

        # НОВАЯ ЛОГИКА: Для новых запросов STORE сразу устанавливаем статус approved
        if is_new and self.request_type == 'STORE':
            self.status = 'approved'

        super().save(*args, **kwargs)

        # Обновляем previous_status после сохранения
        self.previous_status = self.status

    def __str__(self):
        type_info = "для себя" if self.request_type == 'SELF' else f"для магазина {self.store}"
        return f"{self.product.name} — {self.quantity} шт. ({type_info}) от {self.user}"

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