from rest_framework import serializers
from .models import PartnerFinanceStat, StoreFinanceStat, FinanceEntry, CalendarStatistics, ArchivedDailySummary
from apps.stores.models import City


class PartnerFinanceStatSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = PartnerFinanceStat
        fields = ['id', 'user', 'user_name', 'date', 'total_approved_cash', 'total_damaged_loss', 'total_profit']
        read_only_fields = ['user', 'date', 'total_approved_cash', 'total_damaged_loss', 'total_profit']

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"


class StoreFinanceStatSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.name', read_only=True)
    city_name = serializers.CharField(source='store.city.name', read_only=True)

    class Meta:
        model = StoreFinanceStat
        fields = ['id', 'date', 'store', 'store_name', 'city_name', 'total_approved', 'total_damaged', 'total_debt']
        read_only_fields = ['date', 'store', 'total_approved', 'total_damaged', 'total_debt']


class FinanceEntrySerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)

    class Meta:
        model = FinanceEntry
        fields = ['id', 'user', 'date', 'income', 'expense', 'profit', 'city', 'city_name', 'note']
        read_only_fields = ['user', 'profit']

    def validate_income(self, value):
        if value < 0:
            raise serializers.ValidationError("Доход не может быть отрицательным.")
        return value

    def validate_expense(self, value):
        if value < 0:
            raise serializers.ValidationError("Расход не может быть отрицательным.")
        return value

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        # Расчет прибыли выполняется в методе save модели
        return super().create(validated_data)


class CalendarStatisticsSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField(read_only=True)
    store_name = serializers.CharField(source='store.name', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)

    class Meta:
        model = CalendarStatistics
        fields = ['id', 'date', 'user', 'user_name', 'store', 'store_name', 'city', 'city_name',
                  'has_sales', 'has_requests', 'has_expenses', 'has_debt_payment']

    def get_user_name(self, obj):
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}"
        return None


class ArchivedDailySummarySerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = ArchivedDailySummary
        fields = ['id', 'date', 'user', 'user_name', 'total_requests', 'total_sales',
                  'total_expenses', 'total_profit', 'data']
        read_only_fields = ['date', 'user', 'total_requests', 'total_sales',
                            'total_expenses', 'total_profit', 'data']

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"