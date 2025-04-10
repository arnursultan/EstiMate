from rest_framework import serializers
from .models import ProductRequest
from apps.products.models import Product, PartnerProduct
from apps.stores.models import Store


class ProductRequestSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    price_per_unit = serializers.SerializerMethodField(read_only=True)
    total_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    bonus_quantity = serializers.IntegerField(read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    store_name = serializers.SerializerMethodField(read_only=True)
    request_type_display = serializers.CharField(source='get_request_type_display', read_only=True)
    partner_product_info = serializers.SerializerMethodField(read_only=True)
    batch_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = ProductRequest
        fields = [
            'id', 'product', 'product_name', 'user', 'user_email', 'store', 'store_name',
            'request_type', 'request_type_display', 'partner_product', 'partner_product_info',
            'quantity', 'bonus_quantity', 'damaged_quantity', 'is_bonus_marked',
            'payment_method', 'status', 'total_price', 'price_per_unit', 'created_at', 'batch_id'
        ]
        read_only_fields = ['status', 'total_price', 'bonus_quantity', 'created_at', 'is_bonus_marked', 'user',
                            'batch_id']

    def get_store_name(self, obj):
        return obj.store.name if obj.store else None

    def get_price_per_unit(self, obj):
        if obj.request_type == 'SELF' and obj.product:
            return float(obj.product.price)
        elif obj.request_type == 'STORE' and obj.partner_product:
            return float(obj.partner_product.price)
        return 0

    def get_partner_product_info(self, obj):
        if obj.partner_product:
            return {
                'id': obj.partner_product.id,
                'product_name': obj.partner_product.product.name,
                'remaining_quantity': obj.partner_product.remaining_quantity
            }
        return None


class SelfRequestSerializer(serializers.Serializer):
    """Сериализатор для создания запроса 'для себя' (SELF)"""
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)

    def validate_product_id(self, value):
        try:
            product = Product.objects.get(id=value, is_active=True)
            return value
        except Product.DoesNotExist:
            raise serializers.ValidationError("Указанный товар не найден или неактивен")

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Количество должно быть положительным числом")
        return value

    def validate(self, data):
        product_id = data.get('product_id')
        quantity = data.get('quantity')

        # Проверяем наличие достаточного количества товара у админа
        try:
            product = Product.objects.get(id=product_id)
            if product.quantity < quantity:
                raise serializers.ValidationError(
                    {"quantity": f"Недостаточно товара в каталоге. Доступно: {product.quantity}"}
                )
        except Product.DoesNotExist:
            pass  # Уже проверено в validate_product_id

        return data


class StoreRequestSerializer(serializers.Serializer):
    """Сериализатор для создания запроса 'для магазина' (STORE)"""
    partner_product_id = serializers.IntegerField()
    store_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)

    def validate_partner_product_id(self, value):
        try:
            user = self.context['request'].user
            partner_product = PartnerProduct.objects.get(id=value, partner=user)
            return value
        except PartnerProduct.DoesNotExist:
            raise serializers.ValidationError("Указанный товар не найден в вашем каталоге")

    def validate_store_id(self, value):
        try:
            store = Store.objects.get(id=value, status='approved', is_active=True)
            return value
        except Store.DoesNotExist:
            raise serializers.ValidationError("Указанный магазин не найден или не активен")

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Количество должно быть положительным числом")
        return value

    def validate(self, data):
        # Проверяем, достаточно ли товара в каталоге партнера
        try:
            user = self.context['request'].user
            partner_product = PartnerProduct.objects.get(id=data['partner_product_id'], partner=user)

            if data['quantity'] > partner_product.remaining_quantity:
                raise serializers.ValidationError(
                    {
                        "quantity": f"Недостаточно товара в вашем каталоге. Доступно: {partner_product.remaining_quantity}"}
                )
        except PartnerProduct.DoesNotExist:
            pass  # Эта ошибка уже обрабатывается в validate_partner_product_id

        return data


class AdminProductRequestStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductRequest
        fields = ['status']

    def validate_status(self, value):
        if value not in ['approved', 'rejected']:
            raise serializers.ValidationError("Статус может быть только 'approved' или 'rejected'")

        # Если текущий статус уже не pending
        if self.instance and self.instance.status != 'pending':
            raise serializers.ValidationError(
                f"Нельзя изменить статус, так как текущий статус: '{self.instance.get_status_display()}'")

        # Проверяем, что это запрос типа SELF
        if self.instance and self.instance.request_type != 'SELF':
            raise serializers.ValidationError("Можно изменять статус только для запросов типа SELF")

        return value


class PartnerMarkReceivedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductRequest
        fields = ['status']

    def validate_status(self, value):
        if value != 'received':
            raise serializers.ValidationError("Можно только подтвердить получение")

        if self.instance and self.instance.status != 'approved':
            raise serializers.ValidationError("Можно подтвердить получение только для одобренных запросов")

        return value


class ReportDamagedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductRequest
        fields = ['damaged_quantity']

    def validate_damaged_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Брак не может быть отрицательным")

        if self.instance and value > self.instance.quantity:
            raise serializers.ValidationError(
                f"Количество бракованных товаров ({value}) не может превышать общее количество ({self.instance.quantity})")

        return value