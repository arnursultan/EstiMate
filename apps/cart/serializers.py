from rest_framework import serializers
from apps.orders.models import ProductRequest


class CartSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    price_per_unit = serializers.DecimalField(source='product.price', max_digits=10, decimal_places=2, read_only=True)
    product_image = serializers.ImageField(source='product.image', read_only=True)
    is_bonus_eligible = serializers.BooleanField(source='product.is_bonus_eligible', read_only=True)

    class Meta:
        model = ProductRequest
        fields = [
            'id', 'product', 'product_name', 'product_image', 'quantity', 'bonus_quantity',
            'damaged_quantity', 'status', 'total_price', 'price_per_unit', 'is_bonus_eligible',
            'created_at'
        ]
        read_only_fields = ['bonus_quantity', 'status', 'total_price', 'created_at']


class CartReceivedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductRequest
        fields = ['status']

    def validate_status(self, value):
        if value != 'received':
            raise serializers.ValidationError("Статус может быть только 'received'")

        if self.instance.status != 'approved':
            raise serializers.ValidationError("Можно отметить как полученный только одобренный запрос")

        return value


class CartDamagedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductRequest
        fields = ['damaged_quantity']

    def validate_damaged_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Количество бракованных товаров не может быть отрицательным")

        if value > self.instance.quantity:
            raise serializers.ValidationError(
                f"Количество бракованных товаров ({value}) не может превышать общее количество ({self.instance.quantity})")

        return value