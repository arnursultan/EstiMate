from rest_framework import serializers
from .models import ProductRequest


class ProductRequestSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    store_name = serializers.CharField(source='store.name', read_only=True)
    product_price = serializers.DecimalField(source='product.price', read_only=True, max_digits=10, decimal_places=2)

    class Meta:
        model = ProductRequest
        fields = [
            'id', 'product', 'product_name', 'user', 'user_email',
            'quantity', 'bonus_quantity', 'damaged_quantity', 'payment_method',
            'status', 'for_store', 'store', 'store_name',
            'product_price', 'total_price', 'created_at'
        ]
        read_only_fields = [
            'bonus_quantity', 'damaged_quantity', 'status',
            'total_price', 'created_at', 'user'
        ]

    def validate(self, data):
        product = data.get('product')
        quantity = data.get('quantity')
        for_store = data.get('for_store', False)
        store = data.get('store')

        if not for_store and product.quantity < quantity:
            raise serializers.ValidationError(f"Недостаточно товара на складе. Осталось: {product.quantity}")

        if for_store and not store:
            raise serializers.ValidationError("Магазин обязателен при запросе для магазина")

        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class AdminProductRequestStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductRequest
        fields = ['status']

    def validate_status(self, value):
        if self.instance.status != 'pending':
            raise serializers.ValidationError("Можно изменить только запросы со статусом 'pending'")
        if value not in ['approved', 'rejected']:
            raise serializers.ValidationError("Статус должен быть 'approved' или 'rejected'")
        return value


class PartnerMarkReceivedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductRequest
        fields = ['status']

    def validate(self, data):
        if self.instance.status != 'approved':
            raise serializers.ValidationError("Только подтвержденные запросы можно отметить как полученные")
        return data

    def update(self, instance, validated_data):
        instance.status = 'received'
        instance.save()
        return instance


class ReportDamagedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductRequest
        fields = ['damaged_quantity']

    def validate_damaged_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Количество не может быть отрицательным")
        if value > self.instance.quantity:
            raise serializers.ValidationError("Брак превышает запрошенное количество")
        return value

    def update(self, instance, validated_data):
        instance.damaged_quantity = validated_data['damaged_quantity']
        instance.save()
        return instance
