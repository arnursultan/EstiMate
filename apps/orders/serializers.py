from rest_framework import serializers
from .models import ProductRequest
from apps.products.models import Product
from apps.stores.models import Store


class ProductRequestSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    price_per_unit = serializers.DecimalField(source='product.price', max_digits=10, decimal_places=2, read_only=True)
    total_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    bonus_quantity = serializers.IntegerField(read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    store_name = serializers.CharField(source='store.name', read_only=True, allow_null=True)

    class Meta:
        model = ProductRequest
        fields = [
            'id', 'product', 'product_name', 'user', 'user_email', 'store', 'store_name', 'for_store',
            'quantity', 'bonus_quantity', 'damaged_quantity', 'is_bonus_marked',
            'payment_method', 'status', 'total_price', 'price_per_unit', 'created_at'
        ]
        read_only_fields = ['status', 'total_price', 'bonus_quantity', 'created_at', 'is_bonus_marked', 'user']

    def validate(self, data):
        """Валидация данных запроса"""
        product = data.get('product')
        quantity = data.get('quantity')
        for_store = data.get('for_store', False)
        store = data.get('store')
        payment_method = data.get('payment_method', 'cash')

        # Проверка на магазин при for_store=True
        if for_store and not store:
            raise serializers.ValidationError({"store": "Для запроса на магазин необходимо указать магазин"})

        # Проверка статуса и активности магазина
        if store:
            if store.status != 'approved':
                raise serializers.ValidationError({"store": "Можно выбрать только подтвержденные магазины"})

            if not store.is_active:
                raise serializers.ValidationError({"store": "Можно выбрать только активные магазины"})

        # Проверка на долг только для магазинов
        if payment_method == 'debt':
            if not for_store:
                raise serializers.ValidationError({"payment_method": "Оплата в долг доступна только для магазинов"})

            if not store:
                raise serializers.ValidationError({"store": "Для оплаты в долг необходимо выбрать магазин"})

        # Проверка наличия товара на складе, если запрос не для магазина
        if not for_store and product.quantity < quantity:
            raise serializers.ValidationError({"quantity": "Недостаточно товара на складе для выполнения запроса"})

        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


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


class ProductRequestCalculationSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    for_store = serializers.BooleanField(default=False)
    store_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, data):
        try:
            product = Product.objects.get(id=data['product_id'])
        except Product.DoesNotExist:
            raise serializers.ValidationError({"product_id": "Товар не найден"})

        if data['quantity'] <= 0:
            raise serializers.ValidationError({"quantity": "Количество должно быть положительным"})

        # Проверка для магазина
        if data.get('for_store') and data.get('store_id'):
            try:
                store = Store.objects.get(id=data['store_id'])
                if store.status != 'approved':
                    raise serializers.ValidationError({"store_id": "Можно выбрать только подтвержденные магазины"})

                if not store.is_active:
                    raise serializers.ValidationError({"store_id": "Можно выбрать только активные магазины"})

                data['store'] = store
            except Store.DoesNotExist:
                raise serializers.ValidationError({"store_id": "Магазин не найден"})

        # Проверка наличия товара на складе, если запрос не для магазина
        if not data.get('for_store') and product.quantity < data['quantity']:
            raise serializers.ValidationError({"quantity": "Недостаточно товара на складе для выполнения запроса"})

        data['product'] = product
        return data