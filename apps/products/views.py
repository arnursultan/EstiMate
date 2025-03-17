from rest_framework import viewsets, permissions, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Product, ProductImage, ProductCategory
from .serializers import ProductSerializer, ProductImageSerializer
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from django.db.models import Sum


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by("-created_at")
    serializer_class = ProductSerializer
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ["name", "description", "category__name"]
    ordering_fields = ["price", "created_at", "stock"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        user = self.request.user

        category_id = self.request.data.get("category")
        category = get_object_or_404(ProductCategory, id=category_id) if category_id else None

        if user.is_staff:
            stock = serializer.validated_data.get("stock", 0)
            total_stock = Product.objects.filter(name=serializer.validated_data["name"]).aggregate(total_stock=Sum("stock"))[
                "total_stock"] or 0
            if total_stock + stock > 5000:
                raise ValidationError("Администратор не может добавить более 5000 единиц одного товара.")

        serializer.save(owner=user, category=category)

    def perform_update(self, serializer):
        category_id = self.request.data.get("category")
        category = get_object_or_404(ProductCategory, id=category_id) if category_id else None
        serializer.save(category=category)

    @action(detail=False, methods=["GET"], permission_classes=[permissions.AllowAny])
    def bonus(self, request):
        queryset = self.get_queryset().filter(bonus=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ProductImageViewSet(viewsets.ModelViewSet):
    queryset = ProductImage.objects.all()
    serializer_class = ProductImageSerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_create(self, serializer):
        instance = serializer.save()

        if instance.is_main:
            ProductImage.objects.filter(product=instance.product, is_main=True).exclude(id=instance.id).update(
                is_main=False)

            instance.product.main_image = instance.image
            instance.product.save()

    def perform_update(self, serializer):
        instance = serializer.save()

        if instance.is_main:
            ProductImage.objects.filter(product=instance.product, is_main=True).exclude(id=instance.id).update(
                is_main=False)

            instance.product.main_image = instance.image
            instance.product.save()


