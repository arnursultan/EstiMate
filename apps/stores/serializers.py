from rest_framework import serializers
from django.utils import timezone
from django.db import models
from .models import City, Store, StoreDebt


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ['id', 'name']


class StoreSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)

    class Meta:
        model = Store
        fields = [
            'id', 'name', 'inn', 'city', 'city_name',
            'address', 'phone', 'status', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['status', 'is_active', 'created_at', 'updated_at']

    def validate_inn(self, value):
        if len(value) < 10 or len(value) > 14:
            raise serializers.ValidationError("ИНН должен быть от 10 до 14 символов")

        # Проверяем, не существует ли уже магазин с таким ИНН
        query = Store.objects.filter(inn=value)
        if self.instance:
            query = query.exclude(pk=self.instance.pk)

        if query.exists():
            raise serializers.ValidationError("Магазин с таким ИНН уже существует")

        return value

    def validate_phone(self, value):
        if not value.startswith('+') or not value[1:].isdigit():
            raise serializers.ValidationError("Телефон должен быть в формате +XXXXXXXXXXX")
        return value


class StoreDetailSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)
    total_debt = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Store
        fields = [
            'id', 'name', 'inn', 'city', 'city_name',
            'address', 'phone', 'status', 'status_display',
            'is_active', 'total_debt', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_total_debt(self, obj):
        return obj.debts.filter(is_paid=False).aggregate(
            total=models.Sum('amount')
        )['total'] or 0


class StoreStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ['status']

    def validate_status(self, value):
        if value not in ['approved', 'rejected']:
            raise serializers.ValidationError("Статус может быть только 'approved' или 'rejected'")
        if self.instance.status != 'pending':
            raise serializers.ValidationError("Можно обновлять статус только для заявок в состоянии 'pending'")
        return value


class StoreActivationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ['is_active']


class StoreDebtSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.name', read_only=True)

    class Meta:
        model = StoreDebt
        fields = ['id', 'store', 'store_name', 'amount', 'created_at', 'is_paid', 'paid_at']
        read_only_fields = ['created_at', 'is_paid', 'paid_at']


class StoreDebtPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreDebt
        fields = ['is_paid']

    def validate_is_paid(self, value):
        if value is not True:
            raise serializers.ValidationError("Можно только отметить долг как оплаченный")
        return value

    def update(self, instance, validated_data):
        if instance.is_paid:
            raise serializers.ValidationError("Долг уже отмечен как оплаченный")

        instance.mark_as_paid()
        return instance


class DebtPaymentSerializer(serializers.Serializer):
    debt_id = serializers.IntegerField()
    payment_amount = serializers.DecimalField(max_digits=12, decimal_places=2)

    def validate_debt_id(self, value):
        try:
            debt = StoreDebt.objects.get(id=value)
            if debt.is_paid:
                raise serializers.ValidationError("Этот долг уже погашен")
            return value
        except StoreDebt.DoesNotExist:
            raise serializers.ValidationError("Долг с таким ID не найден")

    def validate_payment_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Сумма платежа должна быть положительной")
        return value