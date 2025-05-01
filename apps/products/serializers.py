from rest_framework import serializers
from .models import Product, PartnerInventory
from django.contrib.auth import get_user_model # Импорт User
from decimal import Decimal

User = get_user_model() # Получаем модель User

class ProductSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.00'), coerce_to_string=False)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price',
            'quantity', 'is_bonus', 'is_active', 'is_deleted', # Добавили is_deleted
            'created_at', 'updated_at', 'image', 'image_url'
        ]
        read_only_fields = ['created_at', 'updated_at', 'is_deleted'] # is_deleted read_only
        extra_kwargs = {
            'image': {'write_only': True, 'required': False},
        }

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            # Добавляем базовый URL, если запрос недоступен
            from django.conf import settings
            return f"{settings.BASE_URL}{obj.image.url}" if hasattr(settings, 'BASE_URL') else obj.image.url
        return None

    def validate(self, data):
        # Форматирование названия товара
        name = data.get('name')
        if name:
            name = name.strip()
            if name:
                 data['name'] = name[0].upper() + name[1:]
        return data


class ProductListSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.00'), read_only=True, coerce_to_string=False)

    class Meta:
        model = Product
        # Показываем is_deleted для информации, но фильтруем в ViewSet
        fields = ['id', 'name', 'price', 'quantity', 'is_bonus', 'is_active', 'is_deleted', 'image_url']

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            # Добавляем базовый URL, если запрос недоступен
            from django.conf import settings
            return f"{settings.BASE_URL}{obj.image.url}" if hasattr(settings, 'BASE_URL') else obj.image.url
        return None


# --- НОВЫЕ СЕРИАЛИЗАТОРЫ ---

class PartnerInventorySerializer(serializers.ModelSerializer):
    """Сериализатор для инвентаря партнера (в основном для записи)"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    partner_name = serializers.SerializerMethodField(read_only=True)
    quantity = serializers.IntegerField(min_value=0) # Количество может быть 0
    # product поле должно быть writeable для создания/обновления
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True, is_deleted=False),
        # Убрали limit_choices_to отсюда, т.к. queryset уже фильтрует
        # limit_choices_to={'is_active': True, 'is_deleted': False}
    )


    class Meta:
        model = PartnerInventory
        fields = [
            'id', 'partner', 'partner_name', 'product', 'product_name',
            'quantity', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'partner']

    def get_partner_name(self, obj):
         return f"{obj.partner.first_name} {obj.partner.last_name}" if obj.partner else None

    def validate(self, data):
        # Проверка уникальности пары partner-product при создании
        request = self.context.get('request')
        partner = request.user # Партнер берется из запроса
        product = data.get('product')
        instance = self.instance # Текущий объект (при обновлении)

        # Проверяем только при создании (instance is None)
        if instance is None and product:
            if PartnerInventory.objects.filter(partner=partner, product=product).exists():
                raise serializers.ValidationError({
                    "product": f"Запись инвентаря для товара '{product.name}' у этого партнера уже существует."
                })

        # При обновлении (instance is not None), product менять нельзя
        if instance and 'product' in data and data['product'] != instance.product:
             raise serializers.ValidationError({"product": "Нельзя изменить товар в существующей записи инвентаря."})

        # Проверка, что продукт активен и не удален (уже сделано в queryset для product)

        return data

    def create(self, validated_data):
        # Устанавливаем партнера из запроса
        validated_data['partner'] = self.context['request'].user
        return super().create(validated_data)


class PartnerInventoryDetailSerializer(serializers.ModelSerializer):
    """Расширенный сериализатор для отображения инвентаря партнера"""
    product_id = serializers.IntegerField(source='product.id', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_description = serializers.CharField(source='product.description', read_only=True)
    product_price = serializers.DecimalField(
        source='product.price',
        max_digits=10,
        decimal_places=2,
        read_only=True,
        coerce_to_string=False
    )
    is_bonus = serializers.BooleanField(source='product.is_bonus', read_only=True)
    product_image_url = serializers.SerializerMethodField() # Изменено имя поля
    available_quantity = serializers.IntegerField(source='quantity', read_only=True)
    partner_name = serializers.SerializerMethodField(read_only=True) # Добавим имя партнера

    class Meta:
        model = PartnerInventory
        fields = [
            'id', # ID самой записи инвентаря
            'partner', 'partner_name', # Добавили
            'product', # ID товара для связи
            'product_id', 'product_name', 'product_description',
            'product_price', 'is_bonus', 'available_quantity',
            'product_image_url', 'created_at', 'updated_at'
        ]
        read_only_fields = fields # Все поля только для чтения в этом сериализаторе

    def get_partner_name(self, obj):
         return f"{obj.partner.first_name} {obj.partner.last_name}" if obj.partner else None

    def get_product_image_url(self, obj):
        if obj.product.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.product.image.url)
            from django.conf import settings
            return f"{settings.BASE_URL}{obj.product.image.url}" if hasattr(settings, 'BASE_URL') else obj.product.image.url
        return None
