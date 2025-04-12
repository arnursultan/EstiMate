from rest_framework import serializers
from .models import Product, PartnerInventory, ProductImage


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'is_primary']


class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
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

    class Meta:
        model = PartnerInventory
        fields = [
            'id', 'partner', 'product', 'product_name',
            'product_price', 'is_bonus', 'quantity',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'partner']

    def validate(self, data):
        # Проверка, что продукт существует
        if 'product' in data and data['product'].quantity == 0:
            raise serializers.ValidationError("Товар отсутствует на складе")
        return data

    def create(self, validated_data):
        validated_data['partner'] = self.context['request'].user
        return super().create(validated_data)


class ProductListSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'quantity', 'is_bonus', 'is_active', 'primary_image']

    def get_primary_image(self, obj):
        primary_image = obj.images.filter(is_primary=True).first()
        if primary_image:
            return self.context['request'].build_absolute_uri(primary_image.image.url)
        return None