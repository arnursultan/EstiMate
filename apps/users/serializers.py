import re
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from rest_framework import serializers
from .models import User
import logging

logger = logging.getLogger(__name__)

allowed_domains = ["gmail.com", "mail.ru", "yahoo.com", "yandex.ru", "outlook.com"]

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        ref_name = "UserUserSerializer"
        model = User
        fields = ["id", "email", "phone", "role", "first_name", "last_name", "password", "status"]
        extra_kwargs = {
            "password": {"write_only": True, "required": True},
            "status": {"read_only": True},
            "role": {"read_only": True},
        }

    def validate_email(self, value):

        if len(value) > 50:
            raise serializers.ValidationError("Email не должен превышать 50 символов.")

        email_pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
        if not re.match(email_pattern, value) or ".." in value:
            raise serializers.ValidationError("Некорректный формат email.")

        domain = value.split("@")[-1].lower()
        if domain not in allowed_domains:
            raise serializers.ValidationError(f"Регистрация разрешена только для доменов: {', '.join(allowed_domains)}")

        qs = User.objects.exclude(pk=self.instance.pk) if self.instance else User.objects.all()
        if qs.filter(email=value).exists():
            raise serializers.ValidationError("Пользователь с таким email уже существует.")

        return value

    def validate_phone(self, value):
        if not re.match(r"^\+996\d{9}$", value):
            raise serializers.ValidationError("Телефон должен быть в формате: +996XXXXXXXXX (9 цифр после кода страны).")
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("Пользователь с таким номером телефона уже зарегистрирован.")
        return value

    def validate_first_name(self, value):
        if not value.isalpha():
            raise serializers.ValidationError("Имя должно содержать только буквы.")
        if not (2 <= len(value) <= 24):
            raise serializers.ValidationError("Имя должно быть от 2 до 24 символов.")
        return value.capitalize()

    def validate_last_name(self, value):
        if not value.isalpha():
            raise serializers.ValidationError("Фамилия должна содержать только буквы.")
        if not (2 <= len(value) <= 24):
            raise serializers.ValidationError("Фамилия должна быть от 2 до 24 символов.")
        return value.capitalize()

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Пароль должен быть не менее 8 символов.")
        if not re.search(r"[a-zA-Z]", value) or not re.search(r"\d", value):
            raise serializers.ValidationError("Пароль должен содержать буквы и цифры.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user




class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        ref_name = "UserUpdateSerializer"
        model = User
        fields = ["email", "phone", "first_name", "last_name", "password","photo"]
        extra_kwargs = {
            "password": {"write_only": True, "required": False},
            "email": {"required": False},
            "phone": {"required": False},
            "first_name": {"required": False},
            "last_name": {"required": False},
        }

    def validate_email(self, value):
        if len(value) > 50:
            raise serializers.ValidationError("Email не должен превышать 50 символов.")

        email_pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
        if not re.match(email_pattern, value) or ".." in value:
            raise serializers.ValidationError("Некорректный формат email.")

        domain = value.split("@")[-1].lower()
        if domain not in allowed_domains:
            raise serializers.ValidationError(f"Регистрация разрешена только для доменов: {', '.join(allowed_domains)}")

        qs = User.objects.exclude(pk=self.instance.pk) if self.instance else User.objects.all()
        if qs.filter(email=value).exists():
            raise serializers.ValidationError("Пользователь с таким email уже существует.")

        return value

    def validate_phone(self, value):
        if not re.match(r"^\+996\d{9}$", value):
            raise serializers.ValidationError(
                "Телефон должен быть в формате: +996XXXXXXXXX (9 цифр после кода страны).")
        if User.objects.exclude(pk=self.instance.pk).filter(phone=value).exists():
            raise serializers.ValidationError("Пользователь с таким телефоном уже существует.")
        return value

    def validate_first_name(self, value):
        if not value.isalpha():
            raise serializers.ValidationError("Имя должно содержать только буквы.")
        if not (2 <= len(value) <= 24):
            raise serializers.ValidationError("Имя должно быть от 2 до 24 символов.")
        return value.title()

    def validate_last_name(self, value):
        if not value.isalpha():
            raise serializers.ValidationError("Фамилия должна содержать только буквы.")
        if not (2 <= len(value) <= 24):
            raise serializers.ValidationError("Фамилия должна быть от 2 до 24 символов.")
        return value.title()

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Пароль должен быть не менее 8 символов.")
        if not re.search(r"[a-zA-Z]", value) or not re.search(r"\d", value):
            raise serializers.ValidationError("Пароль должен содержать буквы и цифры.")
        return value

    def validate_photo(self, value):
        max_size_mb = 5
        if value.size > max_size_mb * 1024 * 1024:
            raise serializers.ValidationError(f"Размер фото не должен превышать {max_size_mb}MB.")
        if not value.content_type.startswith("image/"):
            raise serializers.ValidationError("Файл должен быть изображением (jpeg, png и др.).")
        return value

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()
        return instance

class UserDetailSerializer(serializers.ModelSerializer):
    photo = serializers.ImageField(read_only=True)
    class Meta:
        ref_name = "UserDetailSerializer"
        model = User
        fields = ["id", "email", "phone", "role", "first_name", "last_name", "status","photo"]



User = get_user_model()

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Неверный email")

        if not check_password(password, user.password):
            raise serializers.ValidationError("Неверный пароль.")

        if not user.is_active:
            raise serializers.ValidationError("Ваш аккаунт заблокирован или неактивен.")

        if user.status == 'pending':
            raise serializers.ValidationError("Ваш аккаунт еще не одобрен администратором.")

        if user.status == 'rejected':
            raise serializers.ValidationError("Ваша заявка была отклонена администратором.")

        data['user'] = user
        return data


class UserPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["photo"]

    def validate_photo(self, value):

        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Размер фото не должен превышать 5MB.")

        allowed_types = ["image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"]
        if value.content_type not in allowed_types:
            raise serializers.ValidationError("Недопустимый формат изображения. Разрешены: JPEG, PNG, WEBP, HEIC.")

        return value