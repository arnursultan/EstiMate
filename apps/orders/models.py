from django.db import models
from django.core.validators import MinValueValidator
from apps.users.models import User
from apps.products.models import Product
from apps.stores.models import Store
from django.db.models import Sum


class Order(models.Model):
    """Модель заказа"""
    ORDER_STATUS = [
        ('in_process', 'В обработке'),
        ('confirmed', 'Подтвержден'),
        ('rejected', 'Отклонен'),
    ]
    ORDER_TYPE = [
        ('admin_to_partner', 'От администратора к партнеру'),
        ('partner_to_store', 'От партнера к магазину'),
    ]

    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="orders_created",
        verbose_name="Создатель заказа"
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="orders",
        null=True,
        blank=True,
        verbose_name="Магазин"
    )
    partner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="orders_received",
        verbose_name="Партнер"
    )
    status = models.CharField(
        max_length=20,
        choices=ORDER_STATUS,
        default='in_process',
        verbose_name="Статус заказа"
    )
    order_type = models.CharField(
        max_length=20,
        choices=ORDER_TYPE,
        verbose_name="Тип заказа"
    )
    is_group_order = models.BooleanField(
        default=True,
        verbose_name="Групповой заказ"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ['-created_at']

    def __str__(self):
        order_type = "Групповой" if self.is_group_order else "Одиночный"
        if self.order_type == 'admin_to_partner':
            return f"{order_type} заказ партнера {self.partner.first_name} ({self.get_status_display()})"
        else:
            return f"{order_type} заказ магазина {self.store.name} ({self.get_status_display()})"

    @property
    def total_price(self):
        """Расчет общей стоимости заказа"""
        return sum(item.total_price for item in self.order_items.all())

    @property
    def total_bonus_items(self):
        """Подсчет общего количества бонусных товаров"""
        return self.order_items.aggregate(Sum('bonus_quantity'))['bonus_quantity__sum'] or 0

    def save(self, *args, **kwargs):
        """Переопределение метода сохранения"""
        # Автоматическое подтверждение заказов для магазина
        if self.order_type == 'partner_to_store' and self.status == 'in_process':
            self.status = 'confirmed'

        super().save(*args, **kwargs)


class OrderItem(models.Model):
    """Модель элемента заказа"""
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="order_items",
        verbose_name="Заказ"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="order_items",
        verbose_name="Товар"
    )
    quantity = models.PositiveIntegerField(verbose_name="Количество")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Цена за единицу"
    )
    bonus_quantity = models.PositiveIntegerField(default=0, verbose_name="Бонусное количество")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Элемент заказа"
        verbose_name_plural = "Элементы заказа"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product.name} ({self.quantity} шт.)"

    @property
    def total_price(self):
        """Расчет общей стоимости элемента заказа"""
        return self.price * self.quantity

    def save(self, *args, **kwargs):
        # Проверка, нужно ли рассчитывать бонусы
        if self.product.is_bonus and self.quantity >= 20:
            self.bonus_quantity = self.quantity // 20
        else:
            self.bonus_quantity = 0

        super().save(*args, **kwargs)


class DefectItem(models.Model):
    """Модель бракованных товаров"""
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="defect_items",
        verbose_name="Заказ"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="defect_items",
        verbose_name="Товар"
    )
    quantity = models.PositiveIntegerField(verbose_name="Количество бракованных товаров")
    description = models.TextField(blank=True, verbose_name="Описание дефекта")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Бракованный товар"
        verbose_name_plural = "Бракованные товары"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product.name} ({self.quantity} шт. брак)"

    @property
    def total_price(self):
        """Расчет общей стоимости бракованных товаров"""
        return self.product.price * self.quantity