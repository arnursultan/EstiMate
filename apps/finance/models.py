from django.db import models
from apps.stores.models import Store

class Finance(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="finances")
    income = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    expense = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    bonus = models.PositiveIntegerField(default=0)
    defect = models.PositiveIntegerField(default=0)
    debt = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    payment = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.balance = self.income - self.expense - self.debt + self.payment
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Финансы {self.store.name} - Баланс: {self.balance}"
