from rest_framework import serializers
from .models import CartItem
from apps.products.models import Product, PartnerProduct
from apps.stores.models import Store


class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField(read_only=True)
    price = serializers.SerializerMethodField(read_only=True)
    image = serializers.SerializerMethodField(read_only=True)
    store_name = serializers.CharField(source='store.name', read_only=True, allow_null=True)
    cart_type_display = serializers.CharField(source='get_cart_type_display', read_only=True)

    class Meta:
        model = CartItem
        fields = [
            'id', 'user', 'cart_type', 'cart_type_display', 'product', 'partner_product',
            'store', 'store_name', 'quantity', 'product_name', 'price', 'image',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

    def get_product_name(self, obj):
        if obj.cart_type == 'SELF' and obj.product:
            return obj.product.name
        elif obj.cart_type == 'STORE' and obj.partner_product:
            return obj.partner_product.product.name
        return None

    def get_price(self, obj):
        if obj.cart_type == 'SELF' and obj.product:
            return float(obj.product.price)
        elif obj.cart_type == 'STORE' and obj.partner_product:
            return float(obj.partner_product.price)
        return None

    def get_image(self, obj):
        if obj.cart_type == 'SELF' and obj.product and obj.product.image:
            return obj.product.image.url
        elif obj.cart_type == 'STORE' and obj.partner_product and obj.partner_product.product.image:
            return obj.partner_product.product.image.url
        return None

    def validate(self, data):
        cart_type = data.get('cart_type')
        product = data.get('product')
        partner_product = data.get('partner_product')
        store = data.get('store')

        # Проверки для разных типов запросов
        if cart_type == 'SELF':
            # Для SELF должен быть указан product
            if not product:
                raise serializers.ValidationError({"product": "Для запроса 'для себя' необходимо указать товар"})
            if partner_product:
                raise serializers.ValidationError(
                    {"partner_product": "Для запроса 'для себя' не нужно указывать товар из личного каталога"})
            if store:
                raise serializers.ValidationError({"store": "Для запроса 'для себя' не нужно указывать магазин"})

        elif cart_type == 'STORE':
            # Для STORE должны быть указаны partner_product и store
            if not partner_product:
                raise serializers.ValidationError(
                    {"partner_product": "Для запроса в магазин необходимо указать товар из личного каталога"})
            if not store:
                raise serializers.ValidationError({"store": "Для запроса в магазин необходимо указать магазин"})
            if product:
                raise serializers.ValidationError(
                    {"product": "Для запроса в магазин нельзя указывать товар из глобального каталога"})

            # Проверка, что партнер имеет доступ к выбранному partner_product
            user = self.context.get('request').user
            if partner_product and partner_product.partner.id != user.id:
                raise serializers.ValidationError(
                    {"partner_product": "Вы можете выбрать только товары из вашего личного каталога"}
                )

            # Проверка достаточного количества товара у партнера
            quantity = data.get('quantity', 1)
            if partner_product and quantity > partner_product.remaining_quantity:
                raise serializers.ValidationError(
                    {
                        "quantity": f"Недостаточно товара в вашем каталоге. Доступно: {partner_product.remaining_quantity}"}
                )

            # Проверка статуса и активности магазина
            if store:
                if store.status != 'approved':
                    raise serializers.ValidationError({"store": "Можно выбрать только подтвержденные магазины"})
                if not store.is_active:
                    raise serializers.ValidationError({"store": "Можно выбрать только активные магазины"})

        return data

    def create(self, validated_data):
        # Устанавливаем пользователя из контекста запроса
        validated_data['user'] = self.context['request'].user

        # Проверяем, есть ли уже такой товар в корзине
        cart_type = validated_data.get('cart_type')

        if cart_type == 'SELF':
            product = validated_data.get('product')
            existing_item = CartItem.objects.filter(
                user=validated_data['user'],
                cart_type='SELF',
                product=product
            ).first()

            if existing_item:
                # Увеличиваем количество
                existing_item.quantity += validated_data.get('quantity', 1)
                existing_item.save()
                return existing_item

        elif cart_type == 'STORE':
            partner_product = validated_data.get('partner_product')
            store = validated_data.get('store')
            existing_item = CartItem.objects.filter(
                user=validated_data['user'],
                cart_type='STORE',
                partner_product=partner_product,
                store=store
            ).first()

            if existing_item:
                # Увеличиваем количество
                existing_item.quantity += validated_data.get('quantity', 1)
                existing_item.save()
                return existing_item

        return super().create(validated_data)


class AddToCartSerializer(serializers.Serializer):
    cart_type = serializers.ChoiceField(choices=CartItem.CART_TYPE_CHOICES)
    product_id = serializers.IntegerField(required=False)
    partner_product_id = serializers.IntegerField(required=False)
    store_id = serializers.IntegerField(required=False)
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate(self, data):
        cart_type = data.get('cart_type')
        product_id = data.get('product_id')
        partner_product_id = data.get('partner_product_id')
        store_id = data.get('store_id')

        if cart_type == 'SELF':
            if not product_id:
                raise serializers.ValidationError({"product_id": "Для запроса 'для себя' необходимо указать ID товара"})
            if partner_product_id:
                raise serializers.ValidationError(
                    {"partner_product_id": "Для запроса 'для себя' не нужно указывать ID товара из личного каталога"})
            if store_id:
                raise serializers.ValidationError({"store_id": "Для запроса 'для себя' не нужно указывать ID магазина"})

        elif cart_type == 'STORE':
            if not partner_product_id:
                raise serializers.ValidationError(
                    {"partner_product_id": "Для запроса в магазин необходимо указать ID товара из личного каталога"})
            if not store_id:
                raise serializers.ValidationError({"store_id": "Для запроса в магазин необходимо указать ID магазина"})
            if product_id:
                raise serializers.ValidationError(
                    {"product_id": "Для запроса в магазин нельзя указывать ID товара из глобального каталога"})

        return data


class UpdateCartItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartItem
        fields = ['quantity']

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Количество должно быть положительным числом")

        # Проверка достаточного количества товара у партнера для запросов STORE
        instance = self.instance
        if instance and instance.cart_type == 'STORE' and instance.partner_product:
            if value > instance.partner_product.remaining_quantity:
                raise serializers.ValidationError(
                    f"Недостаточно товара в вашем каталоге. Доступно: {instance.partner_product.remaining_quantity}"
                )

        return value


class CheckoutSerializer(serializers.Serializer):
    cart_type = serializers.ChoiceField(choices=CartItem.CART_TYPE_CHOICES)

    def validate(self, data):
        cart_type = data.get('cart_type')
        user = self.context['request'].user

        # Проверяем, есть ли товары в корзине указанного типа
        cart_items = CartItem.objects.filter(user=user, cart_type=cart_type)
        if not cart_items.exists():
            raise serializers.ValidationError({"cart_type": f"В корзине '{cart_type}' нет товаров"})

        return data