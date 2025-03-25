from django.db import models
from apps.orders.models import ProductRequest
from apps.stores.models import Store, City
from apps.users.models import User


class PartnerFinanceStat(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='finance_stats')
    date = models.DateField(auto_now_add=True)
    total_approved_cash = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_damaged_loss = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        unique_together = ('user', 'date')
        ordering = ['-date']


class StoreFinanceStat(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='finance_stats')
    date = models.DateField(auto_now_add=True)
    total_approved = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_damaged = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_debt = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        unique_together = ('store', 'date')
        ordering = ['-date']


class FinanceEntry(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='manual_finance_entries')
    date = models.DateField(blank=False,null=False)
    income = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expense = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']
