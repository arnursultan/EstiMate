from django.contrib.auth.models import AbstractUser
from django.db import models
import bcrypt

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Администратор'),
        ('partner', 'Партнер'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='partner')
    email = models.EmailField(max_length=50, unique=True)
    phone = models.CharField(max_length=15, unique=True, blank=True, null=True)

    def set_password(self, raw_password):
        self.password = bcrypt.hashpw(raw_password.encode(), bcrypt.gensalt()).decode()

    def check_password(self, raw_password):
        return bcrypt.checkpw(raw_password.encode(), self.password.encode())

    def __str__(self):
        return self.username
