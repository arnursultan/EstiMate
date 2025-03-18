import re
from rest_framework import serializers
from .models import User
import logging
logger = logging.getLogger(__name__)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "login", "phone", "role", "full_name", "password"]
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
        if not re.match(r"^\d{10,15}$", value):
            raise serializers.ValidationError("Телефон должен содержать только цифры (10-15 символов).")
        return value

    def validate_full_name(self, value):
        """ФИО: 15-24 символа"""
        if not (15 <= len(value) <= 24):
            raise serializers.ValidationError("Имя должно быть от 15 до 24 символов.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        print("🔥 StoreSerializer update() вызван!")
        new_payment = validated_data.get("payment", 0)

        if new_payment > 0:
            old_debt = instance.debt
            instance.debt = max(instance.debt - new_payment, 0)
            instance.payment += new_payment

            if instance.debt == 0:
                instance.status = "closed"

            logger.info(
                f"[{instance.updated_at}] Магазин {instance.name} внес {new_payment} KGS, "
                f"долг был {old_debt}, стал {instance.debt}."
            )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance
