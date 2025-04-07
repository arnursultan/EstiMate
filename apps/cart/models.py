from django.db import models
from apps.users.models import User
from apps.products.models import Product, PartnerProduct


# Модифицируем модель CartItem в apps/cart/models.py

class CartItem(models.Model):
    CART_TYPE_CHOICES = (
        ('SELF', 'Для себя'),
        ('STORE', 'Для магазина'),
    )

    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='cart_items')
    cart_type = models.CharField(max_length=5, choices=CART_TYPE_CHOICES, default='SELF')

    # Для запросов типа SELF
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cart_items'
    )

    # Для запросов типа STORE
    partner_product = models.ForeignKey(
        'products.PartnerProduct',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cart_items'
    )

    # Для запросов типа STORE
    store = models.ForeignKey(
        'stores.Store',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cart_items'
    )

    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Связь с запросом
    product_request = models.ForeignKey(
        'orders.ProductRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cart_items'
    )

    class Meta:
        verbose_name = "Элемент корзины"
        verbose_name_plural = "Элементы корзины"
        ordering = ['-created_at']