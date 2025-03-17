import logging
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

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
    inn = models.CharField(max_length=14, unique=True, validators=[validate_inn], verbose_name="ИНН")
    city = models.CharField(max_length=50, choices=[("Ош", "Ош"), ("Джалал-Абад", "Джалал-Абад"), ("Баткен", "Баткен")], verbose_name="Город")
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
            if old_store.payment != self.payment:
                old_debt = self.debt
                self.debt = max(self.debt - self.payment, 0)

                logger.info(
                    f"💰 Магазин {self.name} внес {self.payment} KGS. Долг был {old_debt}, стал {self.debt}."
                )

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.status})"

    class Meta:
        verbose_name = "Магазин"
        verbose_name_plural = "Магазины"
