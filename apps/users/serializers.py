import re
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from rest_framework import serializers
from .models import User
from .validators import (
    validate_email, validate_phone, validate_first_name,
    validate_last_name, validate_password, validate_photo
)
import logging

logger = logging.getLogger(__name__)

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
        return validate_email(value, self.instance)

    def validate_phone(self, value):
        return validate_phone(value, self.instance)

    def validate_first_name(self, value):
        return validate_first_name(value)

    def validate_last_name(self, value):
        return validate_last_name(value)

    def validate_password(self, value):
        return validate_password(value)

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
        return validate_email(value, self.instance)

    def validate_phone(self, value):
        return validate_phone(value, self.instance)

    def validate_first_name(self, value):
        return validate_first_name(value)

    def validate_last_name(self, value):
        return validate_last_name(value)

    def validate_password(self, value):
        return validate_password(value)

    def validate_photo(self, value):
        return validate_photo(value)


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



class UserPutSerializer(serializers.ModelSerializer):
    class Meta:
        ref_name = "UserPutSerializer"
        model = User
        fields = ["email", "phone", "first_name", "last_name", "password", "photo"]
        extra_kwargs = {
            "password": {"write_only": True},
        }

    def validate_email(self, value):
        return validate_email(value, self.instance)

    def validate_phone(self, value):
        return validate_phone(value, self.instance)

    def validate_first_name(self, value):
        return validate_first_name(value)

    def validate_last_name(self, value):
        return validate_last_name(value)

    def validate_password(self, value):
        return validate_password(value)

    def validate_photo(self, value):
        return validate_photo(value)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance