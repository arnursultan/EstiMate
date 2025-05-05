# Обновление файла apps/users/models.py

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinLengthValidator, MaxLengthValidator
from django.db import models
import re
from model_utils import FieldTracker

class UserManager(BaseUserManager):
    def create_user(self, email, phone, first_name, last_name, password=None, role="partner", status="pending",
                    **extra_fields):
        if not email:
            raise ValueError("У пользователя должен быть email")
        if not self.validate_email(email):
            raise ValueError("Некорректный формат email")

        email = self.normalize_email(email)

        # Приведение имени и фамилии к правильному формату
        first_name = self._format_name(first_name)
        last_name = self._format_name(last_name)

        user = self.model(email=email, phone=phone, first_name=first_name, last_name=last_name, role=role,
                          status=status, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, phone, first_name, last_name, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("status", "approved")
        extra_fields.setdefault("role", "admin")
        return self.create_user(email, phone, first_name, last_name, password, **extra_fields)

    @staticmethod
    def validate_email(email):
        email_regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        return len(email) <= 50 and re.match(email_regex, email)

    @staticmethod
    def _format_name(name):
        """Форматирует имя или фамилию - первая буква заглавная, остальные строчные"""
        if not name:
            return ""
        name = name.strip()
        return name[0].upper() + name[1:].lower() if name else ""


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ("admin", "Администратор"),
        ("partner", "Партнер"),
    ]
    STATUS_CHOICES = [
        ("pending", "Ожидает одобрения"),
        ("approved", "Одобрено"),
        ("rejected", "Отклонено"),
    ]

    email = models.EmailField(max_length=50, unique=True, verbose_name="Email")
    phone = models.CharField(max_length=15, unique=True, blank=True, null=True, verbose_name="Телефон")

    first_name = models.CharField(
        max_length=24,
        validators=[
            MinLengthValidator(2, message="Имя должно быть не менее 2 символов"),
            MaxLengthValidator(24, message="Имя должно быть не более 24 символов")
        ],
        verbose_name="Имя"
    )

    last_name = models.CharField(
        max_length=24,
        validators=[
            MinLengthValidator(2, message="Фамилия должна быть не менее 2 символов"),
            MaxLengthValidator(24, message="Фамилия должна быть не более 24 символов")
        ],
        verbose_name="Фамилия"
    )
    photo = models.ImageField(upload_to='users/photos/', default="users/photos/default.jpg", blank=True, null=True,
                              verbose_name="Фото профиля")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="partner", verbose_name="Роль")
    token_reset = models.CharField(max_length=5, blank=True, null=True, verbose_name="Токен сброса пароля")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending", verbose_name="Статус аккаунта")
    tracker = FieldTracker(fields=['status'])
    is_active = models.BooleanField(default=True, verbose_name="Активный")
    is_staff = models.BooleanField(default=False, verbose_name="Сотрудник")
    # Добавляем поле для мягкого удаления
    is_deleted = models.BooleanField(default=False, verbose_name="Удален")

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["phone", "first_name", "last_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_role_display()})"

    class Meta:
        verbose_name = "Пользователя"
        verbose_name_plural = "Пользователи"

    def save(self, *args, **kwargs):
        """Переопределение save для автоматического форматирования имени и фамилии"""
        # Форматирование имени и фамилии - первая буква заглавная, остальные строчные
        if self.first_name:
            self.first_name = self.first_name.strip()
            if self.first_name:
                self.first_name = self.first_name[0].upper() + self.first_name[1:].lower()

        if self.last_name:
            self.last_name = self.last_name.strip()
            if self.last_name:
                self.last_name = self.last_name[0].upper() + self.last_name[1:].lower()

        super().save(*args, **kwargs)

    @classmethod
    def get_active(cls):
        """Получить всех активных и не удаленных пользователей"""
        return cls.objects.filter(is_active=True, is_deleted=False)

    def soft_delete(self):
        """Мягкое удаление пользователя"""
        self.is_deleted = True
        self.save(update_fields=['is_deleted'])
        return True

    def restore(self):
        """Восстановление пользователя"""
        self.is_deleted = False
        self.save(update_fields=['is_deleted'])
        return True