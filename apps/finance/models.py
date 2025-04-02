from django.db import models
from django.core.exceptions import ValidationError
from apps.orders.models import ProductRequest
from apps.stores.models import Store, City
from apps.users.models import User


class PartnerFinanceStat(models.Model):
    """Статистика по финансам партнера"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='finance_stats')
    date = models.DateField(auto_now_add=True)
    total_approved_cash = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_damaged_loss = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        unique_together = ('user', 'date')
        ordering = ['-date']
        verbose_name = "Финансовая статистика партнера"
        verbose_name_plural = "Финансовая статистика партнеров"

    def __str__(self):
        return f"{self.user} - {self.date}: {self.total_profit}"


class StoreFinanceStat(models.Model):
    """Статистика по финансам магазина"""
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='finance_stats')
    date = models.DateField(auto_now_add=True)
    total_approved = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_damaged = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_debt = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        unique_together = ('store', 'date')
        ordering = ['-date']
        verbose_name = "Финансовая статистика магазина"
        verbose_name_plural = "Финансовая статистика магазинов"

    def __str__(self):
        return f"{self.store} - {self.date}: {self.total_approved}"


class FinanceEntry(models.Model):
    """Ручные финансовые записи"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='manual_finance_entries')
    date = models.DateField(blank=False, null=False)
    income = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expense = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']
        verbose_name = "Финансовая запись"
        verbose_name_plural = "Финансовые записи"

    def __str__(self):
        return f"{self.user} - {self.date}: Доход={self.income}, Расход={self.expense}"

    def save(self, *args, **kwargs):
        # Автоматический расчет прибыли
        self.profit = self.income - self.expense
        super().save(*args, **kwargs)


class CalendarStatistics(models.Model):
    """Модель для хранения меток календаря с данными"""
    date = models.DateField(verbose_name="Дата")
    has_sales = models.BooleanField(default=False, verbose_name="Были продажи")
    has_requests = models.BooleanField(default=False, verbose_name="Были запросы")
    has_expenses = models.BooleanField(default=False, verbose_name="Были расходы")
    has_debt_payment = models.BooleanField(default=False, verbose_name="Были погашения долгов")

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='calendar_marks',
        null=True,
        blank=True,
        verbose_name="Партнер"
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name='calendar_marks',
        null=True,
        blank=True,
        verbose_name="Магазин"
    )
    city = models.ForeignKey(
        City,
        on_delete=models.CASCADE,
        related_name='calendar_marks',
        null=True,
        blank=True,
        verbose_name="Город"
    )

    class Meta:
        unique_together = ('date', 'user', 'store', 'city')
        verbose_name = "Метка календаря"
        verbose_name_plural = "Метки календаря"
        ordering = ['-date']

    def __str__(self):
        entity = self.user or self.store or self.city or "Общие данные"
        return f"{entity} - {self.date}"


class ArchivedDailySummary(models.Model):
    """Архивная сводка данных по дням для партнера"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='archived_summaries')
    date = models.DateField()

    total_requests = models.IntegerField(default=0)
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    data = models.JSONField(default=dict, blank=True)  # Дополнительные данные

    class Meta:
        unique_together = ('user', 'date')
        verbose_name = "Архивная сводка"
        verbose_name_plural = "Архивные сводки"
        ordering = ['-date']

    def __str__(self):
        return f"{self.user} - {self.date}: Прибыль={self.total_profit}"