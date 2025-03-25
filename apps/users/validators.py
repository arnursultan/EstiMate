
import re
from rest_framework import serializers

allowed_domains = ["gmail.com", "mail.ru", "yahoo.com", "yandex.ru", "outlook.com"]


def validate_email(value, instance=None):
    if len(value) > 50:
        raise serializers.ValidationError("Email не должен превышать 50 символов.")

    email_pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
    if not re.match(email_pattern, value) or ".." in value:
        raise serializers.ValidationError("Некорректный формат email.")

    domain = value.split("@")[1].lower()
    if domain not in allowed_domains:
        raise serializers.ValidationError(f"Регистрация разрешена только для доменов: {', '.join(allowed_domains)}")

    from .models import User
    qs = User.objects.exclude(pk=instance.pk) if instance else User.objects.all()
    if qs.filter(email=value).exists():
        raise serializers.ValidationError("Пользователь с таким email уже существует.")

    return value


def validate_phone(value, instance=None):
    if not re.match(r"^\+996\d{9}$", value):
        raise serializers.ValidationError("Телефон должен быть в формате: +996XXXXXXXXX (9 цифр после кода страны).")

    from .models import User
    qs = User.objects.exclude(pk=instance.pk) if instance else User.objects.all()
    if qs.filter(phone=value).exists():
        raise serializers.ValidationError("Пользователь с таким телефоном уже существует.")
    return value


def validate_first_name(value):
    if not value.isalpha():
        raise serializers.ValidationError("Имя должно содержать только буквы.")
    if not (2 <= len(value) <= 24):
        raise serializers.ValidationError("Имя должно быть от 2 до 24 символов.")
    return value.capitalize()


def validate_last_name(value):
    if not value.isalpha():
        raise serializers.ValidationError("Фамилия должна содержать только буквы.")
    if not (2 <= len(value) <= 24):
        raise serializers.ValidationError("Фамилия должна быть от 2 до 24 символов.")
    return value.capitalize()


def validate_password(value):
    if len(value) < 8:
        raise serializers.ValidationError("Пароль должен быть не менее 8 символов.")
    if not re.search(r"[a-zA-Z]", value) or not re.search(r"\d", value):
        raise serializers.ValidationError("Пароль должен содержать буквы и цифры.")
    return value


def validate_photo(value):
    max_size_mb = 5
    if value.size > max_size_mb * 1024 * 1024:
        raise serializers.ValidationError(f"Размер фото не должен превышать {max_size_mb}MB.")
    if not value.content_type.startswith("image/"):
        raise serializers.ValidationError("Файл должен быть изображением (jpeg, png и др.).")
    return value
