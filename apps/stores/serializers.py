import re
from django.core.exceptions import ValidationError
from rest_framework import serializers
from .models import Store, Application
from apps.finance.models import Finance

class ApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ['full_name', 'phone_number', 'inn', 'city', 'address', 'title', 'status', 'created_at']

    def validate_phone_number(self, value):
        """
        Валидация для номера телефона.
        Проверяем, чтобы номер телефона был в формате +996 и 9 цифр.
        """
        if not re.match(r"^\+996\d{9}$", value):  # Для Кыргызстана
            raise ValidationError("Неверный формат номера телефона. Например: +996777123456")
        return value

    def validate_inn(self, value):
        """
        Валидация для ИНН.
        Проверяем, чтобы ИНН был длиной 14 символов.
        """
        if len(value) != 14:
            raise ValidationError("ИНН должен содержать 14 символов.")
        return value

    def validate_title(self, value):
        """
        Валидация для названия магазина.
        Название магазина не может быть пустым или слишком коротким.
        """
        if not value:
            raise ValidationError("Название магазина обязательно.")
        if len(value) < 3:
            raise ValidationError("Название магазина должно быть не менее 3 символов.")
        return value

    def create(self, validated_data):
        """
        Создание заявки. Устанавливаем владельца заявки как текущего пользователя.
        """
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)

class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ['name', 'inn', 'city', 'address', 'contact_name', 'phone', 'owner', 'debt', 'payment_total', 'status', 'created_at', 'updated_at', 'debt_limit']

    def validate_phone(self, value):
        """
        Валидация для номера телефона.
        Проверяем, чтобы номер телефона был в формате +996 и 9 цифр.
        """
        if not re.match(r"^\+996\d{9}$", value):  # Для Кыргызстана
            raise ValidationError("Неверный формат номера телефона. Например: +996777123456")
        return value

    def validate_inn(self, value):
        """
        Валидация для ИНН.
        Проверяем, чтобы ИНН был длиной 14 символов.
        """
        if len(value) != 14:
            raise ValidationError("ИНН должен содержать 14 символов.")
        return value