from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Store(models.Model):
    CITY_CHOICES = [
        ('Ош', 'Ош'),
        ('Джалал-Абад', 'Джалал-Абад'),
        ('Баткен', 'Баткен'),
    ]

    name = models.CharField(max_length=255)
    inn = models.CharField(max_length=14, unique=True)
    city = models.CharField(max_length=50, choices=CITY_CHOICES)
    debt = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.BooleanField(default=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="stores")

    def __str__(self):
        return f"{self.name} ({self.city})"
