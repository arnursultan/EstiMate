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
            'status', 'created_at', 'updated_at', 'total_debt',
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

        return data

    def create(self, validated_data):
        if self.context['request'].user.role == 'partner':
            validated_data['partner'] = self.context['request'].user
        return super().create(validated_data)


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
            'status', 'remaining_debt'
        ]

    def get_partner_name(self, obj):
        return f"{obj.partner.first_name} {obj.partner.last_name}"