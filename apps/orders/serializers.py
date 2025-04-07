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
    store_name = serializers.CharField(source='store.name', read_only=True, allow_null=True)
    request_type_display = serializers.CharField(source='get_request_type_display', read_only=True)
    partner_product_info = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ProductRequest
        fields = [
            'id', 'product', 'product_name', 'user', 'user_email', 'store', 'store_name',
            'request_type', 'request_type_display', 'partner_product', 'partner_product_info',
            'quantity', 'bonus_quantity', 'damaged_quantity', 'is_bonus_marked',
            'payment_method', 'status', 'total_price', 'price_per_unit', 'created_at'
        ]
        read_only_fields = ['status', 'total_price', 'bonus_quantity', 'created_at', 'is_bonus_marked', 'user']

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

    def validate(self, data):
        """Валидация данных запроса"""
        product = data.get('product')
        quantity = data.get('quantity')
        request_type = data.get('request_type', 'SELF')
        store = data.get('store')
        partner_product = data.get('partner_product')
        payment_method = data.get('payment_method', 'debt')

        # Проверки для разных типов запросов
        if request_type == 'SELF':
            # Для SELF не нужны store и partner_product
            if store or partner_product:
                raise serializers.ValidationError(
                    {"request_type": "Для запроса 'для себя' не нужно указывать магазин и товар из личного каталога"}
                )

            # Проверка наличия продукта
            if not product:
                raise serializers.ValidationError({"product": "Необходимо указать товар"})

        elif request_type == 'STORE':
            # Для STORE нужны store и partner_product
            if not store:
                raise serializers.ValidationError({"store": "Для запроса в магазин необходимо указать магазин"})

            if not partner_product:
                raise serializers.ValidationError(
                    {"partner_product": "Для запроса в магазин необходимо указать товар из личного каталога"}
                )

            # Проверка статуса и активности магазина
            if store:
                if store.status != 'approved':
                    raise serializers.ValidationError({"store": "Можно выбрать только подтвержденные магазины"})

                if not store.is_active:
                    raise serializers.ValidationError({"store": "Можно выбрать только активные магазины"})

            # Проверка, что партнер имеет доступ к выбранному partner_product
            user = self.context.get('request').user
            if partner_product and partner_product.partner.id != user.id:
                raise serializers.ValidationError(
                    {"partner_product": "Вы можете выбрать только товары из вашего личного каталога"}
                )

            # Проверка достаточного количества товара у партнера
            if partner_product and quantity > partner_product.remaining_quantity:
                raise serializers.ValidationError(
                    {
                        "quantity": f"Недостаточно товара в вашем каталоге. Доступно: {partner_product.remaining_quantity}"}
                )

        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


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