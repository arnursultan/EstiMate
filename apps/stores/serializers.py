from rest_framework import serializers
from django.utils import timezone
from .models import City, Store, StoreDebt, StoreDebtPayment, StoreExpense


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ['id', 'name']


class StoreSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)
    partner_name = serializers.SerializerMethodField()
    total_debt = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        read_only=True,
    )
    total_paid_debt = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        read_only=True,
    )
    remaining_debt = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = Store
        fields = [
            'id', 'name', 'inn', 'phone', 'city', 'city_name',
            'address', 'expenses', 'partner', 'partner_name',
            'status', 'is_active', 'is_deleted', 'created_at', 'updated_at', 'total_debt',
            'total_paid_debt', 'remaining_debt'
        ]
        read_only_fields = ['created_at', 'updated_at', 'partner', 'total_debt', 'total_paid_debt', 'remaining_debt']

    def get_partner_name(self, obj):
        return f"{obj.partner.first_name} {obj.partner.last_name}"

    def validate(self, data):
        # Проверка ИНН
        inn = data.get('inn')
        if inn and len(inn) < 10:
            raise serializers.ValidationError("ИНН должен содержать не менее 10 цифр")

        # Проверка телефона
        phone = data.get('phone')
        if phone and not phone.startswith('+'):
            raise serializers.ValidationError("Номер телефона должен начинаться с +")

        # Устанавливаем статус approved и is_deleted=False
        data['status'] = 'approved'
        data['is_deleted'] = False

        return data

    def create(self, validated_data):
        if self.context['request'].user.role == 'partner':
            validated_data['partner'] = self.context['request'].user
        return super().create(validated_data)


class StoreListSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)
    partner_name = serializers.SerializerMethodField()
    remaining_debt = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = Store
        fields = [
            'id', 'name', 'city_name', 'partner', 'partner_name',
            'status', 'remaining_debt', 'is_active', 'is_deleted',
            'inn', 'phone'
        ]

    def get_partner_name(self, obj):
        return f"{obj.partner.first_name} {obj.partner.last_name}"


class StoreDebtSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.name', read_only=True)

    class Meta:
        model = StoreDebt
        fields = [
            'id', 'store', 'store_name', 'amount', 'description',
            'is_paid', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, data):
        amount = data.get('amount')
        if amount and amount <= 0:
            raise serializers.ValidationError("Сумма долга должна быть больше нуля")
        return data


class DateRangeSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    date = serializers.DateField(required=False)
    city_id = serializers.IntegerField(required=False)

    def validate(self, data):
        if 'date' not in data and ('start_date' not in data or 'end_date' not in data):
            data['date'] = timezone.now().date()
        return data


class StoreStatisticsSerializer(serializers.Serializer):
    store_id = serializers.IntegerField()
    store_name = serializers.CharField()
    date_range = serializers.DictField()
    orders_count = serializers.IntegerField()
    total_ordered_quantity = serializers.IntegerField()
    total_ordered_price = serializers.FloatField()
    total_bonus_quantity = serializers.IntegerField()
    total_defect_quantity = serializers.IntegerField()
    total_defect_price = serializers.FloatField()
    total_debt = serializers.FloatField()
    total_paid_debt = serializers.FloatField()
    remaining_debt = serializers.FloatField()
    period_debt = serializers.FloatField()
    period_paid = serializers.FloatField()
    period_expenses = serializers.FloatField()
    profit = serializers.FloatField()
    products = serializers.ListField(child=serializers.DictField())


class MultipleStoresStatisticsSerializer(serializers.Serializer):
    date_range = serializers.DictField()
    stores_count = serializers.IntegerField()
    orders_count = serializers.IntegerField()
    total_ordered_quantity = serializers.IntegerField()
    total_ordered_price = serializers.FloatField()
    total_bonus_quantity = serializers.IntegerField()
    total_defect_quantity = serializers.IntegerField()
    total_defect_price = serializers.FloatField()
    total_debt = serializers.FloatField()
    total_paid_debt = serializers.FloatField()
    remaining_debt = serializers.FloatField()
    period_debt = serializers.FloatField()
    period_paid = serializers.FloatField()
    period_expenses = serializers.FloatField()
    profit = serializers.FloatField()
    stores = serializers.ListField(child=serializers.DictField())