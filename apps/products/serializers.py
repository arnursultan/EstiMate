from rest_framework import serializers
from .models import Product, PartnerInventory, ProductImage


class ProductImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'is_primary', 'image_url']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if request and obj.image:
            return request.build_absolute_uri(obj.image.url)
        return None


class ProductSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()
    upload_images = serializers.ListField(
        child=serializers.ImageField(),
        required=False,
        write_only=True
    )

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price',
            'quantity', 'is_bonus', 'is_active', 'created_at',
            'updated_at', 'images', 'upload_images'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_images(self, obj):
        # Получаем все изображения продукта и передаем контекст
        images = obj.images.all()
        return ProductImageSerializer(
            images,
            many=True,
            context=self.context
        ).data

    def create(self, validated_data):
        upload_images = validated_data.pop('upload_images', [])
        product = Product.objects.create(**validated_data)

        for i, image in enumerate(upload_images):
            is_primary = (i == 0)  # Первое изображение будет основным
            ProductImage.objects.create(
                product=product,
                image=image,
                is_primary=is_primary
            )

        return product

    def update(self, instance, validated_data):
        upload_images = validated_data.pop('upload_images', [])

        # Обновляем данные товара
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Добавляем новые изображения
        if upload_images:
            has_primary = instance.images.filter(is_primary=True).exists()
            for i, image in enumerate(upload_images):
                # Если еще нет основного изображения, делаем первое загруженное основным
                is_primary = (i == 0 and not has_primary)
                ProductImage.objects.create(
                    product=instance,
                    image=image,
                    is_primary=is_primary
                )

        return instance


class PartnerInventorySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_price = serializers.DecimalField(
        source='product.price',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    is_bonus = serializers.BooleanField(source='product.is_bonus', read_only=True)
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = PartnerInventory
        fields = [
            'id', 'partner', 'product', 'product_name',
            'product_price', 'is_bonus', 'quantity',
            'primary_image', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'partner']

    def get_primary_image(self, obj):
        primary_image = obj.product.images.filter(is_primary=True).first()
        request = self.context.get('request')
        if primary_image and request:
            return request.build_absolute_uri(primary_image.image.url)
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
    primary_image = serializers.SerializerMethodField()
    all_images = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'quantity', 'is_bonus', 'is_active', 'primary_image', 'all_images']

    def get_primary_image(self, obj):
        primary_image = obj.images.filter(is_primary=True).first()
        request = self.context.get('request')
        if primary_image and request:
            return request.build_absolute_uri(primary_image.image.url)
        return None

    def get_all_images(self, obj):
        images = obj.images.all()
        request = self.context.get('request')
        if request:
            return [request.build_absolute_uri(img.image.url) for img in images]
        return []