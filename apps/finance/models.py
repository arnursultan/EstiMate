from decimal import Decimal
from apps.users.models import User
from apps.stores.models import Store
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone


class FinanceEntry(models.Model):
    """Базовая модель для финансовых операций"""
    ENTRY_TYPES = [
        ('income', 'Доход'),
        ('expense', 'Расход'),
        ('debt', 'Долг'),
        ('debt_payment', 'Оплата долга'),
        ('bonus', 'Бонус'),
        ('defect', 'Брак')
    ]

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Сумма"
    )
    description = models.TextField(blank=True, verbose_name="Описание")
    entry_type = models.CharField(
        max_length=20,
        choices=ENTRY_TYPES,
        verbose_name="Тип записи"
    )
    date = models.DateField(verbose_name="Дата")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Финансовая запись"
        verbose_name_plural = "Финансовые записи"
        ordering = ['-date', '-created_at']
        abstract = True


class PartnerFinanceEntry(FinanceEntry):
    """Финансовая запись партнера"""
    partner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="finance_entries",
        verbose_name="Партнер"
    )

    class Meta:
        verbose_name = "Финансовая запись партнера"
        verbose_name_plural = "Финансовые записи партнеров"

    def __str__(self):
        return f"{self.get_entry_type_display()} - {self.amount} - {self.partner.first_name}"


class StoreFinanceEntry(FinanceEntry):
    """Финансовая запись магазина"""
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="finance_entries",
        verbose_name="Магазин"
    )

    class Meta:
        verbose_name = "Финансовая запись магазина"
        verbose_name_plural = "Финансовые записи магазинов"

    def __str__(self):
        return f"{self.get_entry_type_display()} - {self.amount} - {self.store.name}"


class DailyStatistics(models.Model):
    """Ежедневная статистика для более быстрого доступа к данным"""
    date = models.DateField(verbose_name="Дата")

    # Для партнера
    partner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="daily_statistics",
        null=True,
        blank=True,
        verbose_name="Партнер"
    )

    # Для магазина
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="daily_statistics",
        null=True,
        blank=True,
        verbose_name="Магазин"
    )

    # Общие показатели
    total_income = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Общий доход")
    total_expense = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Общие расходы")
    total_debt = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Общий долг")
    total_debt_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Погашенные долги")
    total_bonus_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Сумма бонусов")
    total_bonus_items = models.PositiveIntegerField(default=0, verbose_name="Количество бонусных товаров")
    total_defect_items = models.PositiveIntegerField(default=0, verbose_name="Количество бракованных товаров")
    total_remaining_items = models.PositiveIntegerField(default=0, verbose_name="Остаток товаров")
    total_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Общий баланс")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Ежедневная статистика"
        verbose_name_plural = "Ежедневная статистика"
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(
                fields=['date', 'partner', 'store'],
                name='unique_daily_statistics'
            )
        ]

    def __str__(self):
        if self.partner:
            return f"Статистика {self.partner.first_name} за {self.date}"
        elif self.store:
            return f"Статистика {self.store.name} за {self.date}"
        return f"Общая статистика за {self.date}"


class ProductDailyStatistics(models.Model):
    """Ежедневная статистика по товарам"""
    statistics = models.ForeignKey(
        DailyStatistics,
        on_delete=models.CASCADE,
        related_name="product_stats",
        verbose_name="Основная статистика"
    )
    product_id = models.PositiveIntegerField(verbose_name="ID товара")
    product_name = models.CharField(max_length=255, verbose_name="Название товара")
    requested_quantity = models.PositiveIntegerField(default=0, verbose_name="Запрошенное количество")
    sold_quantity = models.PositiveIntegerField(default=0, verbose_name="Проданное количество")
    bonus_quantity = models.PositiveIntegerField(default=0, verbose_name="Бонусное количество")
    defect_quantity = models.PositiveIntegerField(default=0, verbose_name="Бракованное количество")
    remaining_quantity = models.PositiveIntegerField(default=0, verbose_name="Остаток")
    income_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Сумма дохода")

    class Meta:
        verbose_name = "Статистика товара"
        verbose_name_plural = "Статистика товаров"
        constraints = [
            models.UniqueConstraint(
                fields=['statistics', 'product_id'],
                name='unique_product_daily_statistics'
            )
        ]

    def __str__(self):
        return f"{self.product_name} - {self.statistics.date}"



class ManualFinanceEntry(models.Model):
    """Модель для ручного ввода финансовых данных (расходы, доходы и т.д.)"""
    ENTRY_TYPES = [
        ('income', 'Доход'),
        ('expense', 'Расход'),
        ('other', 'Другое'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='manual_finance_entries',
        verbose_name='Пользователь'
    )
    entry_type = models.CharField(
        max_length=10,
        choices=ENTRY_TYPES,
        default='expense',
        verbose_name='Тип записи'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Сумма'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    date = models.DateField(
        default=timezone.now,
        verbose_name='Дата'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Финансовая запись'
        verbose_name_plural = 'Финансовые записи'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.get_entry_type_display()} ({self.amount}) - {self.date}"


class FinanceStatistics(models.Model):
    """Модель для хранения рассчитанной статистики"""
    date = models.DateField(
        unique=True,
        verbose_name='Дата'
    )
    total_orders = models.IntegerField(
        default=0,
        verbose_name='Всего заказов'
    )
    total_sales = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Всего продаж'
    )
    total_expenses = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Всего расходов'
    )
    total_defects = models.IntegerField(
        default=0,
        verbose_name='Всего бракованных товаров'
    )
    total_bonuses = models.IntegerField(
        default=0,
        verbose_name='Всего бонусных товаров'
    )
    data_json = models.JSONField(
        default=dict,
        verbose_name='Дополнительные данные (JSON)'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    class Meta:
        verbose_name = 'Финансовая статистика'
        verbose_name_plural = 'Финансовая статистика'
        ordering = ['-date']

    def __str__(self):
        return f"Статистика за {self.date}"