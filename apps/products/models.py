from django.db import models

class Product(models.Model):
    CATEGORY_CHOICES = [
        ('electronics', 'Электроника'),
        ('clothing', 'Одежда'),
        ('food', 'Продукты'),
        ('other', 'Другое'),
    ]

    name = models.CharField(max_length=255)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    description = models.TextField(max_length=255, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    stock = models.PositiveIntegerField()
    bonus = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.bonus:
            count = Product.objects.count() + 1
            self.bonus = count % 21 == 0
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({'Бонус' if self.bonus else 'Обычный'})"
