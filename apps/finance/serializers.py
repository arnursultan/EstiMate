from rest_framework import serializers
from .models import (
    PartnerFinanceEntry,
    StoreFinanceEntry,
    DailyStatistics,
    ProductDailyStatistics
)
from apps.stores.models import Store
from django.utils import timezone
from decimal import Decimal


class PartnerFinanceEntrySerializer(serializers.ModelSerializer):
    """Сериализатор для финансовых записей партнера"""
    partner_name = serializers.SerializerMethodField()
    entry_type_display = serializers.CharField(source='get_entry_type_display', read_only=True)

    class Meta:
        model = PartnerFinanceEntry
        fields = [
            'id', 'partner', 'partner_name', 'amount', 'description',
            'entry_type', 'entry_type_display', 'date', 'created_at'
        ]
        read_only_fields = ['created_at']

    def get_partner_name(self, obj):
        return f"{obj.partner.first_name} {obj.partner.last_name}"

    def validate(self, data):
        if not data.get('date'):
            data['date'] = timezone.now().date()

        if data.get('amount', 0) <= 0:
            raise serializers.ValidationError("Сумма должна быть больше нуля")

        return data


class StoreFinanceEntrySerializer(serializers.ModelSerializer):
    """Сериализатор для финансовых записей магазина"""
    store_name = serializers.CharField(source='store.name', read_only=True)
    entry_type_display = serializers.CharField(source='get_entry_type_display', read_only=True)

    class Meta:
        model = StoreFinanceEntry
        fields = [
            'id', 'store', 'store_name', 'amount', 'description',
            'entry_type', 'entry_type_display', 'date', 'created_at'
        ]
        read_only_fields = ['created_at']

    def validate(self, data):
        if not data.get('date'):
            data['date'] = timezone.now().date()

        if data.get('amount', 0) <= 0:
            raise serializers.ValidationError("Сумма должна быть больше нуля")

        # Проверка доступа к магазину для партнеров
        request = self.context.get('request')
        if request and request.user.role == 'partner':
            store = data.get('store')
            if store and store.partner != request.user:
                raise serializers.ValidationError("У вас нет доступа к этому магазину")

        return data


class ProductDailyStatisticsSerializer(serializers.ModelSerializer):
    """Сериализатор для детальной статистики по товарам"""

    class Meta:
        model = ProductDailyStatistics
        fields = [
            'product_id', 'product_name', 'requested_quantity', 'sold_quantity',
            'bonus_quantity', 'defect_quantity', 'remaining_quantity', 'income_amount'
        ]


class DailyStatisticsSerializer(serializers.ModelSerializer):
    """Сериализатор для ежедневной статистики"""
    product_stats = ProductDailyStatisticsSerializer(many=True, read_only=True)
    store_name = serializers.SerializerMethodField(read_only=True)
    partner_name = serializers.SerializerMethodField(read_only=True)
    city = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DailyStatistics
        fields = [
            'id', 'date', 'partner', 'partner_name', 'store', 'store_name', 'city',
            'total_income', 'total_expense', 'total_debt', 'total_debt_paid',
            'total_bonus_amount', 'total_bonus_items', 'total_defect_items',
            'total_remaining_items', 'total_balance', 'product_stats'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_store_name(self, obj):
        return obj.store.name if obj.store else None

    def get_partner_name(self, obj):
        if obj.partner:
            return f"{obj.partner.first_name} {obj.partner.last_name}"
        return None

    def get_city(self, obj):
        return obj.store.city if obj.store else None


class FinanceSummarySerializer(serializers.Serializer):
    """Сериализатор для финансовой сводки"""
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    total_income = serializers.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_expense = serializers.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_debt = serializers.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_debt_paid = serializers.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_bonus_items = serializers.IntegerField(default=0)
    total_defect_items = serializers.IntegerField(default=0)
    total_balance = serializers.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    product_summaries = serializers.ListField(child=serializers.DictField(), default=list)


class StoreFilterSerializer(serializers.Serializer):
    """Сериализатор для фильтрации по магазинам"""
    store_id = serializers.IntegerField(required=False)
    city = serializers.CharField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def validate(self, data):
        # Проверка доступа к магазину для партнеров
        request = self.context.get('request')
        if request and request.user.role == 'partner' and 'store_id' in data:
            try:
                store = Store.objects.get(id=data['store_id'])
                if store.partner != request.user:
                    raise serializers.ValidationError("У вас нет доступа к этому магазину")
            except Store.DoesNotExist:
                raise serializers.ValidationError("Магазин не найден")

        # Установка дат по умолчанию, если не указаны
        if 'date_from' not in data and 'date_to' not in data:
            data['date_from'] = timezone.now().date()
            data['date_to'] = timezone.now().date()
        elif 'date_from' in data and 'date_to' not in data:
            data['date_to'] = data['date_from']
        elif 'date_to' in data and 'date_from' not in data:
            data['date_from'] = data['date_to']

        return data