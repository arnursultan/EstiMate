from django.db import models
from django.core.validators import MinValueValidator
from apps.users.models import User
from decimal import Decimal

class Product(models.Model):
    """Модель товара"""
    name = models.CharField(max_length=100, verbose_name="Название товара")
    description = models.TextField(verbose_name="Описание товара")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))], # Цена может быть 0
        verbose_name="Цена"
    )
    quantity = models.PositiveIntegerField(default=0, verbose_name="Количество на складе")
    image = models.ImageField(upload_to='products/', null=True, blank=True, verbose_name="Изображение товара")
    is_bonus = models.BooleanField(default=False, verbose_name="Участвует в бонусной программе")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    # Убедись, что поле is_deleted существует
    is_deleted = models.BooleanField(default=False, verbose_name="Удален")

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ['name'] # Изменим сортировку на имя

    def __str__(self):
        status_deleted = " (Удален)" if self.is_deleted else ""
        status_active = "" if self.is_active else " (Неактивен)"
        return f"{self.name} - {self.price} сом{status_active}{status_deleted}"

    def save(self, *args, **kwargs):
        """Переопределение save для автоматического форматирования названия товара"""
        if self.name:
            self.name = self.name.strip()
            if self.name:
                 # Первая буква заглавная, остальные как есть (или lower)
                self.name = self.name[0].upper() + self.name[1:]

        # Убираем форматирование описания, т.к. оно может содержать разную разметку
        # if self.description:
        #     self.description = self.description.strip()
        #     if self.description:
        #         self.description = self.description[0].upper() + self.description[1:]

        super().save(*args, **kwargs)

    @classmethod
    def get_active(cls):
        """Получить все активные и не удаленные товары"""
        return cls.objects.filter(is_active=True, is_deleted=False)

    def soft_delete(self):
        """Мягкое удаление товара"""
        if self.is_deleted:
            return False
        self.is_deleted = True
        self.is_active = False # Деактивируем
        self.save(update_fields=['is_deleted', 'is_active'])
        return True

    def restore(self):
        """Восстановление товара"""
        if not self.is_deleted:
            return False
        self.is_deleted = False
        self.is_active = True # Активируем
        self.save(update_fields=['is_deleted', 'is_active'])
        return True


class PartnerInventory(models.Model):
    """Модель инвентаря партнера"""
    partner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="inventory",
        limit_choices_to={'role': 'partner'}, # Ограничение для админки
        verbose_name="Партнер"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="partner_inventories",
        # Ограничим выбор только активными и не удаленными товарами
        limit_choices_to={'is_active': True, 'is_deleted': False},
        verbose_name="Товар"
    )
    quantity = models.PositiveIntegerField(default=0, verbose_name="Количество")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Инвентарь партнера"
        verbose_name_plural = "Инвентарь партнеров"
        unique_together = ['partner', 'product']
        ordering = ['partner', 'product__name'] # Добавим сортировку

    def __str__(self):
        return f"{self.partner.email} - {self.product.name} ({self.quantity})"