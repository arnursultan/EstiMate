from django.db import models
from django.core.validators import MinValueValidator
from apps.users.models import User
from django.db.models import Sum


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
        ('pending', 'Ожидает одобрения'),
        ('approved', 'Одобрен'),
        ('rejected', 'Отклонен'),
    ]

    name = models.CharField(max_length=100, verbose_name="Название магазина")
    inn = models.CharField(max_length=20, verbose_name="ИНН")
    phone = models.CharField(max_length=15, verbose_name="Телефон")
    city = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        related_name="stores",
        verbose_name="Город"
    )
    address = models.CharField(max_length=200, verbose_name="Адрес")
    expenses = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Расходы"
    )
    partner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="stores",
        verbose_name="Партнер"
    )
    status = models.CharField(
        max_length=10,
        choices=APPROVAL_STATUS,
        default='pending',
        verbose_name="Статус"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Магазин"
        verbose_name_plural = "Магазины"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.city})"

    @property
    def total_debt(self):
        """Общая сумма всех долгов магазина"""
        return self.debts.aggregate(Sum('amount'))['amount__sum'] or 0

    @property
    def total_paid_debt(self):
        """Общая сумма оплаченных долгов магазина"""
        return self.debt_payments.aggregate(Sum('amount'))['amount__sum'] or 0

    @property
    def remaining_debt(self):
        """Оставшаяся сумма долга"""
        return self.total_debt - self.total_paid_debt


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
        validators=[MinValueValidator(0)],
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
        validators=[MinValueValidator(0)],
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

        # После сохранения платежа проверяем, полностью ли погашен долг
        store = self.store
        if store.total_paid_debt >= store.total_debt:
            # Если общие выплаты больше или равны сумме долга, отмечаем все долги как оплаченные
            store.debts.filter(is_paid=False).update(is_paid=True)


class StoreExpense(models.Model):
    """Модель расходов магазина"""
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="expense_records",
        verbose_name="Магазин"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Сумма расхода"
    )
    description = models.TextField(blank=True, verbose_name="Описание расхода")
    expense_date = models.DateField(verbose_name="Дата расхода")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Расход магазина"
        verbose_name_plural = "Расходы магазинов"
        ordering = ['-expense_date', '-created_at']

    def __str__(self):
        return f"{self.store.name} - Расход {self.amount} сом ({self.expense_date})"

    def save(self, *args, **kwargs):
        """При сохранении расхода увеличиваем общие расходы магазина"""
        super().save(*args, **kwargs)

        # Обновляем общую сумму расходов магазина
        self.store.expenses += self.amount
        self.store.save(update_fields=['expenses'])