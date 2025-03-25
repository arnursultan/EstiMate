from rest_framework import serializers
from .models import PartnerFinanceStat, StoreFinanceStat, FinanceEntry


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

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
