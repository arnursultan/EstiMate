from django.db import models
from django.contrib.auth import get_user_model
from apps.stores.models import Store
from apps.products.models import Product

User = get_user_model()

class OrderRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'В ожидании'),
        ('approved', 'Подтверждена'),
        ('rejected', 'Отклонена'),
    ]

    partner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="orders")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="orders")
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Заказ {self.id}: {self.product.name} ({self.status})"
