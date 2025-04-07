from rest_framework import serializers
from .models import Product, PartnerProduct


class ProductSerializer(serializers.ModelSerializer):
    quantity_available = serializers.IntegerField(source='quantity', read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'price', 'image', 'quantity', 'quantity_available',
                  'created_at', 'is_bonus_eligible', 'is_active']
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
                  'is_bonus_eligible', 'is_active', 'created_at', 'updated_at']
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


# Обновляем PartnerProductSerializer в apps/products/serializers.py

class PartnerProductSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_description = serializers.CharField(source='product.description', read_only=True)
    product_image = serializers.ImageField(source='product.image', read_only=True)
    remaining_quantity = serializers.IntegerField(read_only=True)

    # Добавляем поле для отслеживания связанных запросов в магазины
    pending_store_requests = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PartnerProduct
        fields = [
            'id', 'partner', 'product', 'product_name', 'product_description',
            'product_image', 'quantity', 'sold_quantity', 'damaged_quantity',
            'bonus_quantity', 'returned_quantity', 'remaining_quantity',
            'pending_store_requests', 'price', 'created_at', 'updated_at'
        ]
        read_only_fields = ['partner', 'product', 'created_at', 'updated_at']

    def get_pending_store_requests(self, obj):
        """Возвращает количество ожидающих запросов для магазинов на этот товар"""
        from apps.orders.models import ProductRequest
        return ProductRequest.objects.filter(
            partner_product=obj,
            request_type='STORE',
            status='pending'
        ).count()


class PartnerProductUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор для ручного обновления количества товара партнером"""

    class Meta:
        model = PartnerProduct
        fields = ['sold_quantity', 'damaged_quantity', 'returned_quantity']

    def validate(self, data):
        instance = self.instance

        # Проверка на оставшееся количество при обновлении проданных и бракованных товаров
        sold_delta = data.get('sold_quantity', instance.sold_quantity) - instance.sold_quantity
        damaged_delta = data.get('damaged_quantity', instance.damaged_quantity) - instance.damaged_quantity

        if sold_delta + damaged_delta > instance.remaining_quantity:
            raise serializers.ValidationError("Недостаточно товара для указанных операций")

        # Проверка на возвраты
        returned_delta = data.get('returned_quantity', instance.returned_quantity) - instance.returned_quantity
        if returned_delta > instance.sold_quantity:
            raise serializers.ValidationError("Возврат не может превышать проданное количество")

        return data