from django.db import models
from apps.users.models import User


class City(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Название города")

    class Meta:
        verbose_name = "Город"
        verbose_name_plural = "Города"
        ordering = ['name']

    def __str__(self):
        return self.name


class Store(models.Model):
    STATUS_CHOICES = (
        ('pending', 'На рассмотрении'),
        ('approved', 'Подтвержден'),
        ('rejected', 'Отклонен'),
    )

    name = models.CharField(max_length=255, verbose_name="Название магазина")
    inn = models.CharField(max_length=14, unique=True, verbose_name="ИНН")
    city = models.ForeignKey(
        City,
        on_delete=models.CASCADE,
        related_name='stores',
        verbose_name="Город"
    )
    address = models.CharField(max_length=255, verbose_name="Адрес")
    phone = models.CharField(max_length=15, verbose_name="Телефон")
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
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
        return f"{self.name} (ИНН: {self.inn})"

class StoreDebt(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='debts')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    request = models.ForeignKey('orders.ProductRequest', on_delete=models.SET_NULL,
                                null=True, blank=True, related_name='debts')
    created_at = models.DateTimeField(auto_now_add=True)
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Долг магазина"
        verbose_name_plural = "Долги магазинов"

    def __str__(self):
        status = "Оплачен" if self.is_paid else "Не оплачен"
        return f"{self.store.name}: {self.amount} сом ({status})"
