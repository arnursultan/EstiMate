from rest_framework import serializers
from .models import Product, ProductImage
from django.db.models import Sum


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "is_main", "product"]

    def validate(self, data):
        product = self.instance.product if self.instance else data.get("product")

        if data.get("is_main", False):
            if ProductImage.objects.filter(product=product, is_main=True).exclude(id=self.instance.id if self.instance else None).exists():
                raise serializers.ValidationError("Товар уже имеет основное изображение! Удалите старое или обновите его.")

        return data


class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, required=False)
    is_bonus = serializers.BooleanField(source="bonus", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "price",
            "currency",
            "category",
            "status",
            "stock",
            "is_bonus",
            "created_at",
            "updated_at",
            "images",
        ]

    def create(self, validated_data):
        images_data = self.context["request"].data.get("images", [])
        product = Product.objects.create(**validated_data)

        for image_data in images_data:
            ProductImage.objects.create(product=product, image=image_data["image"], is_main=image_data.get("is_main", False))

        return product

    def validate(self, data):
        user = self.context["request"].user

        if user.is_staff:
            existing_stock = Product.objects.filter(name=data["name"]).aggregate(total_stock=Sum("stock"))[
                "total_stock"] or 0
            if existing_stock + data["stock"] > 5000:
                raise serializers.ValidationError("Администратор не может добавить более 5000 единиц одного товара.")

        return data

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)
