from rest_framework import serializers
from .models import Product, ProductImage


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'order']


class ProductSerializer(serializers.ModelSerializer):
    additional_images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'quantity',
            'is_bonus', 'image', 'weight', 'expiry_months',
            'is_active', 'created_at', 'updated_at', 'additional_images'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_price(self, value):
        """
        Проверка, что цена не отрицательная.
        """
        if value < 0:
            raise serializers.ValidationError("Цена не может быть отрицательной.")
        return value

    def validate_quantity(self, value):
        """
        Проверка, что количество не отрицательное.
        """
        if value < 0:
            raise serializers.ValidationError("Количество не может быть отрицательным.")
        return value


class ProductAdminSerializer(ProductSerializer):
    """
    Сериализатор для администраторов с доступом к изменению всех полей.
    """

    class Meta(ProductSerializer.Meta):
        fields = ProductSerializer.Meta.fields
        read_only_fields = ['created_at', 'updated_at']


class ProductPartnerSerializer(ProductSerializer):
    """
    Сериализатор для партнеров с ограниченным доступом (только чтение).
    """

    class Meta(ProductSerializer.Meta):
        fields = ProductSerializer.Meta.fields
        read_only_fields = ['name', 'description', 'price', 'is_bonus',
                            'weight', 'expiry_months', 'is_active',
                            'created_at', 'updated_at', 'quantity']