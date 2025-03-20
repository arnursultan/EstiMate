from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from apps.finance.models import Finance
import logging

logger = logging.getLogger("store_payments")


def validate_inn(value):
    if not value.isdigit():
        raise ValidationError("ИНН должен содержать только цифры.")
    if not (10 <= len(value) <= 14):
        raise ValidationError("ИНН должен быть от 10 до 14 символов.")


class Store(models.Model):
    STATUS_CHOICES = [
        ("active", "Активен"),
        ("inactive", "Неактивен"),
    ]

    name = models.CharField(max_length=255, verbose_name="Название магазина")
    inn = models.CharField(max_length=14, unique=True, verbose_name="ИНН")
    city = models.CharField(
        max_length=50,
        choices=[("Ош", "Ош"), ("Джалал-Абад", "Джалал-Абад"), ("Баткен", "Баткен")],
        verbose_name="Город"
    )
    debt = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Долг")
    payment = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Погашение")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active", verbose_name="Статус")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Владелец")
    order = models.OneToOneField("orders.OrderRequest", on_delete=models.CASCADE, null=True, blank=True, verbose_name="Заявка")

    def save(self, *args, **kwargs):
        if self.pk:
            old_store = Store.objects.get(pk=self.pk)
            new_payment = self.payment - old_store.payment
            new_debt = self.debt - old_store.debt

            if new_payment > 0 and old_store.debt == 0:
                logger.info(f"💰 Магазин {self.name} оплатил наличными: {new_payment} KGS.")

                Finance.objects.create(
                    store=self,
                    income=new_payment,
                    expense=0,
                    debt=0,
                    payment=0,
                    bonus=0,
                    defect=0,
                )

            # ✅ Бонусные товары
            if hasattr(self, "bonus_items") and self.bonus_items > 0:
                logger.info(f"🎁 Магазин {self.name} получил бонусных товаров: {self.bonus_items} шт.")

                Finance.objects.create(
                    store=self,
                    income=0,
                    expense=0,
                    debt=0,
                    payment=0,
                    bonus=self.bonus_items,
                    defect=0,
                )

            # ✅ Новый долг
            if new_debt < 0:
                logger.info(f"🏦 Магазин {self.name} оформил новый долг: {abs(new_debt)} KGS.")

                Finance.objects.create(
                    store=self,
                    income=0,
                    expense=0,
                    debt=self.debt,
                    payment=0,
                    bonus=0,
                    defect=0,
                )

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.status})"

    class Meta:
        verbose_name = "Магазин"
        verbose_name_plural = "Магазины"
