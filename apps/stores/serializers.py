from rest_framework import serializers
from .models import Store

class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = '__all__'

    def validate_inn(self, value):
        if not value.isdigit() or len(value) != 14:
            raise serializers.ValidationError("ИНН должен содержать 14 цифр.")
        return value
