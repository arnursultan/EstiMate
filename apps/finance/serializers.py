from rest_framework import serializers
from .models import Finance

class FinanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Finance
        fields = '__all__'
        read_only_fields = ['balance', 'created_at']

    def validate_debt(self, value):
        if value < 0:
            raise serializers.ValidationError("Долг не может быть отрицательным!")
        return value
