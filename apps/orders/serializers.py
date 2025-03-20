from rest_framework import serializers
from .models import OrderRequest

class OrderRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderRequest
        fields = '__all__'
        read_only_fields = ['status', 'created_at', 'partner']

    def validate(self, data):
        order_type = data.get("order_type")
        if order_type == "store":
            if not data.get("store_name") or not data.get("inn") or not data.get("city"):
                raise serializers.ValidationError("Для заказа в магазин нужно указать название, ИНН и город.")

        return data

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user:
            validated_data['partner'] = request.user
        return super().create(validated_data)
