from rest_framework import serializers
from .models import PartnerFinanceStat, StoreFinanceStat, FinanceEntry
from ..stores.models import City


class PartnerFinanceStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerFinanceStat
        fields = ['date', 'total_approved_cash', 'total_damaged_loss', 'total_profit']


class StoreFinanceStatSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.name', read_only=True)

    class Meta:
        model = StoreFinanceStat
        fields = ['date', 'store', 'store_name', 'total_approved', 'total_damaged', 'total_debt']


class FinanceEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = FinanceEntry
        fields = ['id', 'user', 'date', 'income', 'expense', 'profit', 'city', 'note']
        read_only_fields = ['user']

    def validate_income(self, value):
        if value < 0:
            raise serializers.ValidationError("Доход не может быть отрицательным.")
        return value

    def validate_expense(self, value):
        if value < 0:
            raise serializers.ValidationError("Расход не может быть отрицательным.")
        return value

    def validate_profit(self, value):
        if value < 0:
            raise serializers.ValidationError("Прибыль не может быть отрицательной.")
        return value

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
