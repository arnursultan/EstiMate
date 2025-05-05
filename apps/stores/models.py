from django.db import models
from django.core.validators import MinValueValidator
from apps.users.models import User
from django.db.models import Sum
from decimal import Decimal # Убедись, что импортирован Decimal


class City(models.Model):
    """Модель города"""
    name = models.CharField(max_length=100, unique=True, verbose_name="Название города")

    class Meta:
        verbose_name = "Город"
        verbose_name_plural = "Города"
        ordering = ['name']

    def __str__(self):
        return self.name


class Store(models.Model):
    """Модель магазина"""
    APPROVAL_STATUS = [
        ('pending', 'Ожидает одобрения'), # Оставим, но не будем использовать по умолчанию
        ('approved', 'Одобрен'),
        ('rejected', 'Отклонен'),
    ]

    name = models.CharField(max_length=100, verbose_name="Название магазина", unique=True)
    inn = models.CharField(max_length=20, verbose_name="ИНН", unique=True)
    phone = models.CharField(max_length=15, verbose_name="Телефон")
    city = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        related_name="stores",
        verbose_name="Город"
    )
    address = models.CharField(max_length=200, verbose_name="Адрес")
    # УДАЛЯЕМ поле expenses, т.к. расходы теперь у партнера
    # expenses = models.DecimalField(...)
    partner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="stores",
        limit_choices_to={'role': 'partner'}, # Добавим ограничение при выборе в админке
        verbose_name="Партнер"
    )
    status = models.CharField(
        max_length=10,
        choices=APPROVAL_STATUS,
        default='approved', # По умолчанию одобрен при создании через API
        verbose_name="Статус"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    # Убедись, что поле is_deleted существует
    is_deleted = models.BooleanField(default=False, verbose_name="Удален")

    class Meta:
        verbose_name = "Магазин"
        verbose_name_plural = "Магазины"
        ordering = ['-created_at']

    def __str__(self):
        status_deleted = " (Удален)" if self.is_deleted else ""
        return f"{self.name} ({self.city}){status_deleted}"

    @property
    def total_debt(self):
        """Общая сумма всех долгов магазина"""
        # Фильтруем удаленные магазины, если нужно не считать их долги
        # Но т.к. долги связаны с магазином, они останутся.
        # Лучше фильтровать при агрегации по всем магазинам.
        return self.debts.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

    @property
    def total_paid_debt(self):
        """Общая сумма оплаченных долгов магазина"""
        return self.debt_payments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

    @property
    def remaining_debt(self):
        """Оставшаяся сумма долга"""
        return self.total_debt - self.total_paid_debt

    def save(self, *args, **kwargs):
        # Форматирование названия магазина
        if self.name:
            self.name = self.name.strip()
            if self.name:
                 # Первая буква заглавная, остальные как есть (если так нужно)
                 # или self.name = self.name[0].upper() + self.name[1:].lower()
                self.name = self.name[0].upper() + self.name[1:]
        super().save(*args, **kwargs)

    def soft_delete(self):
        if self.is_deleted:
             return False
        self.is_deleted = True
        self.is_active = False # Деактивируем при удалении
        self.save(update_fields=['is_deleted', 'is_active'])
        return True

    def restore(self):
        if not self.is_deleted:
             return False
        self.is_deleted = False
        self.is_active = True # Активируем при восстановлении
        self.save(update_fields=['is_deleted', 'is_active'])
        return True


class StoreDebt(models.Model):
    """Модель долга магазина"""
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="debts",
        verbose_name="Магазин"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))], # Долг должен быть > 0
        verbose_name="Сумма долга"
    )
    description = models.TextField(blank=True, verbose_name="Описание")
    is_paid = models.BooleanField(default=False, verbose_name="Оплачено")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Долг магазина"
        verbose_name_plural = "Долги магазинов"
        ordering = ['-created_at']

    def __str__(self):
        status = "оплачен" if self.is_paid else "не оплачен"
        return f"{self.store.name} - {self.amount} сом ({status})"


class StoreDebtPayment(models.Model):
    """Модель частичной оплаты долга магазина"""
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="debt_payments",
        verbose_name="Магазин"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))], # Оплата должна быть > 0
        verbose_name="Сумма оплаты"
    )
    description = models.TextField(blank=True, verbose_name="Комментарий к оплате")
    payment_date = models.DateTimeField(auto_now_add=True, verbose_name="Дата оплаты")

    class Meta:
        verbose_name = "Оплата долга"
        verbose_name_plural = "Оплаты долгов"
        ordering = ['-payment_date']

    def __str__(self):
        return f"{self.store.name} - Оплата {self.amount} сом"

    def save(self, *args, **kwargs):
        """Переопределение метода сохранения для проверки оплаты долга"""
        super().save(*args, **kwargs)
        # Проверяем общий баланс долгов магазина после платежа
        store = self.store
        # Используем Decimal для сравнения
        if store.remaining_debt <= Decimal('0.00'):
             # Если общие выплаты больше или равны сумме долга,
             # отмечаем все НЕОПЛАЧЕННЫЕ долги как оплаченные
             store.debts.filter(is_paid=False).update(is_paid=True)