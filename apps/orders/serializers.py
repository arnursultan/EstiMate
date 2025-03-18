from rest_framework import serializers
from .models import OrderRequest

class OrderRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderRequest
        fields = '__all__'
        read_only_fields = ['status', 'created_at', 'partner']

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user:
            validated_data['partner'] = request.user
        return super().create(validated_data)
