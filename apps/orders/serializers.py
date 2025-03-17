from rest_framework import serializers
from .models import OrderRequest

class OrderRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderRequest
        fields = '__all__'
        read_only_fields = ['status', 'created_at']

    def create(self, validated_data):
        return OrderRequest.objects.create(**validated_data)
