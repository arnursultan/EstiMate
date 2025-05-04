# apps/orders/models.py
from django.db import models
from django.core.validators import MinValueValidator
from django.conf import settings # Используем settings для AUTH_USER_MODEL
from decimal import Decimal
from model_utils import FieldTracker # Для отслеживания бонусов
import logging

# Импортируем модели из других приложений ОДИН РАЗ вверху
from apps.users.models import User
from apps.products.models import Product
from apps.stores.models import Store

logger = logging.getLogger(__name__)

class Order(models.Model):
    """Модель заказа"""
    ORDER_STATUS = [
        ('in_process', 'В обработке'),
        ('confirmed', 'Подтвержден'),
        ('rejected', 'Отклонен'),
    ]
    ORDER_TYPE = [
        ('admin_to_partner', 'Админ → Партнер'), # Краткие названия
        ('partner_to_store', 'Партнер → Магазин'),
    ]

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, # Защита от удаления создателя
        related_name="orders_created", null=True,
        verbose_name="Создатель заказа"
    )
    store = models.ForeignKey(
        Store, on_delete=models.SET_NULL, # Защита от удаления магазина
        related_name="orders", null=True, blank=True,
        verbose_name="Магазин (получатель)"
    )
    partner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, # Защита от удаления партнера
        related_name="orders_received", limit_choices_to={'role': 'partner'},
        null=True,
        verbose_name="Партнер (получатель)"
    )
    status = models.CharField(
        max_length=20, choices=ORDER_STATUS, default='in_process',
        db_index=True, verbose_name="Статус заказа" # Добавим индекс
    )
    order_type = models.CharField(
        max_length=20, choices=ORDER_TYPE, db_index=True, # Добавим индекс
        verbose_name="Тип заказа"
    )
    is_group_order = models.BooleanField(default=True, verbose_name="Групповой заказ")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Дата создания") # Добавим индекс
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    # Трекер для отслеживания изменения статуса в сигналах
    tracker = FieldTracker(fields=['status'])

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ['-created_at']

    def __str__(self):
        order_kind = "Групповой" if self.is_group_order else "Одиночный"
        creator_name = f"{self.created_by.first_name} {self.created_by.last_name}" if self.created_by else "N/A"
        if self.order_type == 'admin_to_partner':
            target = f"Партнер: {self.partner.first_name} {self.partner.last_name}" if self.partner else "Партнер удален/не указан"
            return f"Заказ админу #{self.id} от {creator_name} для {target} ({self.get_status_display()})"
        else:
            target = f"Магазин: {self.store.name}" if self.store else "Магазин удален/не указан"
            return f"Заказ в {target} #{self.id} от {creator_name} ({self.get_status_display()})"

    @property
    def total_price(self):
        """Общая стоимость заказа (сумма стоимостей платных товаров)."""
        total = Decimal('0.00')
        # Итерируем по связанным элементам, чтобы использовать их расчет total_price
        for item in self.order_items.all():
             # Учитываем только стоимость платных товаров
             paid_quantity = item.quantity - (item.bonus_quantity or 0)
             if paid_quantity > 0:
                  total += paid_quantity * (item.price or Decimal('0.00'))
        return total

    @property
    def total_bonus_items(self):
        """Общее количество бонусных товаров."""
        result = self.order_items.aggregate(total=models.Sum('bonus_quantity'))
        return result['total'] or 0

    @property
    def total_items_quantity(self):
         """Общее количество всех товарных единиц в заказе (включая бонусы)."""
         result = self.order_items.aggregate(total=models.Sum('quantity'))
         return result['total'] or 0


class OrderItem(models.Model):
    """Модель элемента заказа"""
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="order_items",
        verbose_name="Заказ"
    )
    # --- ИСПОЛЬЗУЕМ SET_NULL ---
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL, # Не удаляем элемент заказа
        null=True,                 # Разрешаем NULL
        blank=True,                # Для админки
        related_name="order_items",
        verbose_name="Товар (на момент заказа)"
    )
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---
    quantity = models.PositiveIntegerField(verbose_name="Количество")
    price = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Цена за единицу (на момент заказа)"
    )
    bonus_quantity = models.PositiveIntegerField(default=0, verbose_name="Бонусное количество")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    tracker = FieldTracker(fields=['quantity', 'product'])

    class Meta:
        verbose_name = "Элемент заказа"
        verbose_name_plural = "Элементы заказа"
        ordering = ['-created_at']

    def __str__(self):
        product_name = self.product.name if self.product else f"Товар ID {self.product_id} (удален)"
        return f"{product_name} ({self.quantity} шт.) в заказе {self.order_id}"

    @property
    def total_price(self):
        """Общая стоимость этого элемента заказа (quantity * price)."""
        # Не учитывает бонусы здесь, т.к. это стоимость всех единиц
        return (self.price or Decimal('0.00')) * self.quantity

    @property
    def paid_items_price(self):
        """Стоимость только ПЛАТНЫХ единиц этого элемента заказа."""
        paid_quantity = self.quantity - (self.bonus_quantity or 0)
        if paid_quantity > 0:
             return (self.price or Decimal('0.00')) * paid_quantity
        return Decimal('0.00')

    def save(self, *args, **kwargs):
        # --- ИСПРАВЛЕННЫЙ РАСЧЕТ БОНУСОВ (каждый 21-й) ---
        recalculate_bonus = False
        if self.pk is None: recalculate_bonus = True
        else:
            if self.tracker.has_changed('quantity') or self.tracker.has_changed('product_id'):
                 recalculate_bonus = True

        if recalculate_bonus:
             if self.product and self.product.is_bonus and self.quantity >= 21:
                  self.bonus_quantity = self.quantity // 21
                  logger.debug(f"Recalculated bonus for OrderItem {self.id or 'new'}: {self.bonus_quantity} (qty {self.quantity})")
             else:
                  if self.bonus_quantity != 0: logger.debug(f"Resetting bonus for OrderItem {self.id} from {self.bonus_quantity} to 0")
                  self.bonus_quantity = 0

        super().save(*args, **kwargs)


class DefectItem(models.Model):
    """Модель бракованных товаров"""
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="defect_items",
        verbose_name="Заказ"
    )
    # --- ИСПОЛЬЗУЕМ SET_NULL ---
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL, # Не удаляем запись о браке
        null=True,                 # Разрешаем NULL
        blank=True,
        related_name="defect_items",
        verbose_name="Товар"
    )
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---
    quantity = models.PositiveIntegerField(verbose_name="Количество бракованных товаров")
    description = models.TextField(blank=True, verbose_name="Описание дефекта")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Бракованный товар"
        verbose_name_plural = "Бракованные товары"
        ordering = ['-created_at']

    def __str__(self):
        product_name = self.product.name if self.product else f"Товар ID {self.product_id} (удален)"
        return f"{product_name} ({self.quantity} шт. брак) в заказе {self.order_id}"

    @property
    def total_price(self):
        """Расчет общей СТОИМОСТИ бракованных товаров (по ТЕКУЩЕЙ цене товара)"""
        if self.product and self.product.price is not None:
            return self.product.price * self.quantity
        return Decimal('0.00')