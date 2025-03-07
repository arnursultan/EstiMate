from rest_framework import serializers
from .models import Product

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'

    def validate_price(self, value):
        """ Проверка, что цена не отрицательная """
        if value < 0:
            raise serializers.ValidationError("Цена не может быть отрицательной!")
        return value
