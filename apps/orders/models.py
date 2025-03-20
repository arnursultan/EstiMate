import logging
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from apps.stores.models import Store

logger = logging.getLogger(__name__)

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

    ORDER_TYPE_CHOICES = [
        ("self", "Для себя"),
        ("store", "Для магазина"),
    ]

    order_type = models.CharField(
        max_length=10,
        choices=ORDER_TYPE_CHOICES,
        default="self",
        verbose_name="Тип заказа",
    )

    partner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Партнёр")
    store_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Название магазина")
    inn = models.CharField(
        max_length=14, unique=True, blank=True, null=True,
        validators=[validate_inn], verbose_name="ИНН"
    )
    city = models.CharField(
        max_length=50, choices=[("Ош", "Ош"), ("Джалал-Абад", "Джалал-Абад"), ("Баткен", "Баткен")],
        blank=True, null=True, verbose_name="Город"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="Статус")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата подачи")
    def approve(self):
        logger.info(f"✅ Подтверждаем заявку: {self.store_name} (ИНН: {self.inn})")
        if self.pk is None:
            self.save()

        store, created = Store.objects.get_or_create(
            inn=self.inn,
            defaults={
                "name": self.store_name,
                "city": self.city,
                "owner": self.partner,
                "status": "active",
                "debt": 0.00,
                "payment": 0.00,
                "order": self
            }
        )

        if created:
            logger.info(f"✅ Магазин {store.name} успешно создан и привязан к заявке {self.id}!")
        else:
            logger.warning(f"⚠ Магазин с ИНН {self.inn} уже существует!")

        self.status = "approved"
        self.save()
        logger.info(f"✅ Заявка {self.store_name} (ИНН: {self.inn}) подтверждена!")

    def __str__(self):
        return f"Заявка {self.store_name or self.partner} - {self.get_status_display()}"
    class Meta:
        verbose_name = "Заявка на регистрацию магазина"
        verbose_name_plural = "Заявки на регистрацию магазинов"
