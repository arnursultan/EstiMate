import re
from rest_framework import serializers
from .models import User
import logging

logger = logging.getLogger(__name__)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        ref_name = "UserUserSerializer"
        model = User
        fields = ["id", "email", "login", "phone", "role", "first_name", "last_name", "password"]
        extra_kwargs = {
            "password": {"write_only": True},
        }

    def validate_email(self, value):
        if len(value) > 50:
            raise serializers.ValidationError("Email не должен превышать 50 символов.")
        if value.count("@") != 1:
            raise serializers.ValidationError("Email должен содержать ровно один '@'.")
        return value

    def validate_login(self, value):
        if value and not re.match(r"^[a-zA-Z0-9._]{3,20}$", value):
            raise serializers.ValidationError("Логин должен содержать только буквы, цифры, '.', '_' (3-20 символов).")
        return value

    def validate_phone(self, value):
        value = value.replace("+", "")  # Убираем "+"
        if not re.match(r"^\d{10,15}$", value):
            raise serializers.ValidationError("Телефон должен содержать только цифры (10-15 символов).")
        return value

    def validate_first_name(self, value):
        if not (2 <= len(value) <= 24):
            raise serializers.ValidationError("Имя должно быть от 2 до 24 символов.")
        return value

    def validate_last_name(self, value):
        if not (2 <= len(value) <= 24):
            raise serializers.ValidationError("Фамилия должна быть от 2 до 24 символов.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if "password" in validated_data:
            instance.set_password(validated_data["password"])

        instance.save()
        return instance



class LoginSerializer(serializers.Serializer):
    login_or_phone_or_email = serializers.CharField()
    password = serializers.CharField(write_only=True)
