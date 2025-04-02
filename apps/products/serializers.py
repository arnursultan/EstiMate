from rest_framework import serializers
from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    quantity_available = serializers.IntegerField(source='quantity', read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'price', 'image', 'quantity', 'quantity_available',
                  'created_at', 'is_bonus_eligible']
        read_only_fields = ['created_at']
        extra_kwargs = {
            'quantity': {'write_only': True}  # Прячем поле quantity и показываем quantity_available для безопасности
        }

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Название не может быть пустым.")
        return value.strip()

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Цена должна быть положительной.")
        return value

    def validate_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Количество не может быть отрицательным.")
        return value

    def validate_description(self, value):
        if not value.strip():
            raise serializers.ValidationError("Описание не может быть пустым.")
        return value.strip()


class ProductDetailSerializer(serializers.ModelSerializer):
    """Подробная информация о товаре"""

    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'price', 'image', 'quantity',
                  'is_bonus_eligible', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class ProductQuantityUpdateSerializer(serializers.Serializer):
    """Сериализатор для обновления количества товара"""
    quantity_to_add = serializers.IntegerField(min_value=1)

    def validate_quantity_to_add(self, value):
        if value <= 0:
            raise serializers.ValidationError("Количество добавляемого товара должно быть положительным числом")
        return value


class ProductBonusSerializer(serializers.Serializer):
    """Сериализатор для расчета бонусов"""
    quantity = serializers.IntegerField(min_value=1)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Количество должно быть положительным числом")
        return value