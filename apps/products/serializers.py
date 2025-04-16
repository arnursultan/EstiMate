from rest_framework import serializers
from .models import Product, PartnerInventory


class ProductSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price',
            'quantity', 'is_bonus', 'is_active', 'created_at',
            'updated_at', 'image', 'image_url'
        ]
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'image': {'write_only': True, 'required': False},
        }

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class PartnerInventorySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_price = serializers.DecimalField(
        source='product.price',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    is_bonus = serializers.BooleanField(source='product.is_bonus', read_only=True)
    product_image = serializers.SerializerMethodField()

    class Meta:
        model = PartnerInventory
        fields = [
            'id', 'partner', 'product', 'product_name',
            'product_price', 'is_bonus', 'quantity',
            'product_image', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'partner']

    def get_product_image(self, obj):
        request = self.context.get('request')
        if obj.product.image and request:
            return request.build_absolute_uri(obj.product.image.url)
        return None

    def validate(self, data):
        # Проверка, что продукт существует и актуален
        if 'product' in data:
            product = data['product']
            if not product.is_active:
                raise serializers.ValidationError(f"Товар '{product.name}' не активен")
            if product.quantity == 0:
                raise serializers.ValidationError("Товар отсутствует на складе")
        return data

    def create(self, validated_data):
        validated_data['partner'] = self.context['request'].user
        return super().create(validated_data)


class ProductListSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'quantity', 'is_bonus', 'is_active', 'image_url']

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None