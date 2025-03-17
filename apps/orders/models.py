from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from apps.stores.models import Store


def validate_inn(value):
    if not value.isdigit():
        raise ValidationError("ИНН должен содержать только цифры.")
    if not (10 <= len(value) <= 14):
        raise ValidationError("ИНН должен быть от 10 до 14 символов.")


class OrderRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "В ожидании"),
        ("approved", "Подтверждена"),
        ("rejected", "Отклонена"),
    ]

    partner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Партнер")
    store_name = models.CharField(max_length=255, verbose_name="Название магазина")
    inn = models.CharField(max_length=14, validators=[validate_inn], verbose_name="ИНН")
    city = models.CharField(max_length=50, choices=[("Ош", "Ош"), ("Джалал-Абад", "Джалал-Абад"), ("Баткен", "Баткен")], verbose_name="Город")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="Статус")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата подачи")

    def approve(self):
        print(f"✅ Подтверждение заявки: {self.store_name} ({self.inn})")

        store, created = Store.objects.get_or_create(
            inn=self.inn,
            defaults={
                "name": self.store_name,
                "city": self.city,
                "owner": self.partner,
                "status": "active",
                "debt": 0.00,
                "payment": 0.00
            }
        )

        if created:
            print(f"✅ Магазин {store.name} создан!")
        else:
            print(f"⚠ Магазин с ИНН {self.inn} уже существует!")

        self.status = "approved"
        self.save()

    def reject(self):
        self.status = "rejected"
        self.save()

    def __str__(self):
        return f"Заявка {self.store_name} - {self.get_status_display()}"

    class Meta:
        verbose_name = "Заявка на регистрацию магазина"
        verbose_name_plural = "Заявки на регистрацию магазинов"

