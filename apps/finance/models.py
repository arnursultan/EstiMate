from django.db import models
from django.apps import apps
from django.utils.timezone import now


class Finance(models.Model):
    store = models.ForeignKey("stores.Store", on_delete=models.CASCADE, verbose_name="Магазин")
    income = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Доход")  # 💰
    expense = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Расход")  # 🛒
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Остаток")  # 🏦
    bonus = models.IntegerField(default=0, verbose_name="Бонусные товары")  # 🎁
    defect = models.IntegerField(default=0, verbose_name="Бракованные товары")  # ❌
    debt = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Долг")  # 🔥
    payment = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Погашение")  # ✅
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата операции")

    def save(self, *args, **kwargs):
        self.balance = self.income - self.expense + self.debt - self.payment
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Финансы"
        verbose_name_plural = "Финансы"
