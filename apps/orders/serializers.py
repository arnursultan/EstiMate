from rest_framework import serializers
from .models import OrderRequest
from apps.products.models import Product

class OrderRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderRequest
        fields = '__all__'
        read_only_fields = ['partner', 'status', 'created_at']

    def validate_quantity(self, value):
        product = self.initial_data.get('product')
        product_obj = Product.objects.get(id=product)
        if value > product_obj.stock:
            raise serializers.ValidationError("Недостаточно товара на складе.")
        return value
