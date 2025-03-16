from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinLengthValidator, MaxLengthValidator
from django.db import models
import re

class UserManager(BaseUserManager):
    def create_user(self, email, phone, password=None, role="partner", **extra_fields):
        if not email:
            raise ValueError("У пользователя должен быть email")
        if not self.validate_email(email):
            raise ValueError("Некорректный формат email")

        email = self.normalize_email(email)
        user = self.model(email=email, phone=phone, role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "admin")
        return self.create_user(email, phone, password, **extra_fields)

    @staticmethod
    def validate_email(email):
        return len(email) <= 50 and email.count("@") == 1

class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ("admin", "Администратор"),
        ("partner", "Партнер"),
    ]

    email = models.EmailField(max_length=50, unique=True, verbose_name="Email")
    login = models.CharField(max_length=50, unique=True, blank=True, null=True, verbose_name="Логин")
    phone = models.CharField(max_length=15, unique=True, blank=True, null=True, verbose_name="Телефон")
    full_name = models.CharField(
        max_length=24,
        validators=[
            MinLengthValidator(15, message="Имя должно быть не менее 15 символов"),
            MaxLengthValidator(24, message="Имя должно быть не более 24 символов")
        ],
        verbose_name="ФИО"
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="partner", verbose_name="Роль")
    token_reset = models.CharField(max_length=5, blank=True, null=True, verbose_name="Токен сброса пароля")
    is_active = models.BooleanField(default=True, verbose_name="Активный")
    is_staff = models.BooleanField(default=False, verbose_name="Сотрудник")

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["phone"]

    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"
