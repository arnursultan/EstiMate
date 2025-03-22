from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Product(models.Model):
    """
    Модель товара в каталоге с поддержкой бонусных товаров.
    """
    name = models.CharField(max_length=255, verbose_name="Название товара")
    description = models.TextField(blank=True, verbose_name="Описание товара")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Цена"
    )
    quantity = models.PositiveIntegerField(default=0, verbose_name="Количество на складе")
    is_bonus = models.BooleanField(default=False, verbose_name="Бонусный товар")
    image = models.ImageField(
        upload_to='products/',
        blank=True,
        null=True,
        verbose_name="Изображение товара"
    )
    weight = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Вес"
    )
    expiry_months = models.PositiveSmallIntegerField(
        default=6,
        validators=[MinValueValidator(1), MaxValueValidator(36)],
        verbose_name="Срок годности (месяцев)"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    def __str__(self):
        bonus_mark = "★" if self.is_bonus else ""
        return f"{self.name} {bonus_mark} - {self.price} сом"

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ['-created_at']


class ProductImage(models.Model):
    """
    Дополнительные изображения товара (если нужно больше одного).
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='additional_images',
        verbose_name="Товар"
    )
    image = models.ImageField(
        upload_to='products/additional/',
        verbose_name="Дополнительное изображение"
    )
    order = models.PositiveSmallIntegerField(default=0, verbose_name="Порядок")

    def __str__(self):
        return f"Изображение {self.order} для {self.product.name}"

    class Meta:
        verbose_name = "Изображение товара"
        verbose_name_plural = "Изображения товаров"
        ordering = ['product', 'order']