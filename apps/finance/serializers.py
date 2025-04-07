from rest_framework import serializers
from .models import (
    PartnerFinanceStat, StoreFinanceStat, FinanceEntry,
    CalendarStatistics, ArchivedDailySummary, InventorySummary
)
from apps.stores.models import City
from apps.products.models import PartnerProduct


class PartnerFinanceStatSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = PartnerFinanceStat
        fields = [
            'id', 'user', 'user_name', 'date', 'total_approved_debt',
            'total_damaged_loss', 'total_bonus_value', 'total_profit',
            'total_expenses', 'total_sold', 'total_sold_quantity'
        ]
        read_only_fields = [
            'user', 'date', 'total_approved_debt', 'total_damaged_loss',
            'total_bonus_value', 'total_profit', 'total_expenses',
            'total_sold', 'total_sold_quantity'
        ]

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"


class StoreFinanceStatSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.name', read_only=True)
    city_name = serializers.CharField(source='store.city.name', read_only=True)
    creator_name = serializers.SerializerMethodField()

    class Meta:
        model = StoreFinanceStat
        fields = ['id', 'store', 'date', 'total_received_quantity', 'total_damaged_quantity',
                  'total_debt', 'total_bonus_quantity', 'total_paid_debt', 'total_partner_expenses',
                  'detailed_data', 'city_name', 'store_name', 'creator_name']
        read_only_fields = [
            'date', 'store', 'total_approved', 'total_damaged', 'total_debt', 'total_bonus', 'total_paid'
        ]

    def get_creator_name(self, obj):
        if obj.store.creator:
            return f"{obj.store.creator.first_name} {obj.store.creator.last_name}"
        return None


class FinanceEntrySerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)
    entry_type_display = serializers.CharField(source='get_entry_type_display', read_only=True)
    partner_product_info = serializers.SerializerMethodField()

    class Meta:
        model = FinanceEntry
        fields = [
            'id', 'user', 'date', 'entry_type', 'entry_type_display', 'amount', 'quantity',
            'city', 'city_name', 'partner_product', 'partner_product_info', 'note'
        ]
        read_only_fields = ['user']

    def get_partner_product_info(self, obj):
        if obj.partner_product:
            return {
                'id': obj.partner_product.id,
                'product_name': obj.partner_product.product.name,
                'price': float(obj.partner_product.price),
                'remaining_quantity': obj.partner_product.remaining_quantity
            }
        return None

    def validate(self, data):
        entry_type = data.get('entry_type')
        partner_product = data.get('partner_product')
        quantity = data.get('quantity', 0)

        # Для записей типа 'sale', 'damage', 'return' нужен partner_product
        if entry_type in ['sale', 'damage', 'return'] and not partner_product:
            raise serializers.ValidationError(
                {
                    "partner_product": f"Для записи типа '{dict(FinanceEntry.ENTRY_TYPE_CHOICES)[entry_type]}' необходимо указать товар из каталога"}
            )

        # Для записей типа 'sale', 'damage', 'return' нужен quantity
        if entry_type in ['sale', 'damage', 'return'] and quantity <= 0:
            raise serializers.ValidationError(
                {
                    "quantity": f"Для записи типа '{dict(FinanceEntry.ENTRY_TYPE_CHOICES)[entry_type]}' необходимо указать положительное количество"}
            )

        # Проверка, что партнер имеет доступ к выбранному partner_product
        if partner_product:
            user = self.context.get('request').user
            if partner_product.partner.id != user.id and not user.is_staff:
                raise serializers.ValidationError(
                    {"partner_product": "Вы можете выбрать только товары из вашего личного каталога"}
                )

        # Проверка достаточного количества товара для записей типа 'sale', 'damage'
        if entry_type in ['sale', 'damage'] and partner_product:
            if quantity > partner_product.remaining_quantity:
                raise serializers.ValidationError(
                    {"quantity": f"Недостаточно товара в каталоге. Доступно: {partner_product.remaining_quantity}"}
                )

        # Проверка достаточного проданного количества для записей типа 'return'
        if entry_type == 'return' and partner_product:
            if quantity > partner_product.sold_quantity:
                raise serializers.ValidationError(
                    {"quantity": f"Возврат не может превышать проданное количество ({partner_product.sold_quantity})"}
                )

        # Для expense и income amount должен быть положительным
        if entry_type in ['expense', 'income']:
            amount = data.get('amount', 0)
            if amount <= 0:
                raise serializers.ValidationError(
                    {"amount": "Сумма должна быть положительной"}
                )

        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class CalendarStatisticsSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField(read_only=True)
    store_name = serializers.CharField(source='store.name', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)

    class Meta:
        model = CalendarStatistics
        fields = [
            'id', 'date', 'user', 'user_name', 'store', 'store_name', 'city', 'city_name',
            'has_sales', 'has_requests', 'has_expenses', 'has_debt_payment',
            'has_damages', 'has_returns'
        ]

    def get_user_name(self, obj):
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}"
        return None


class ArchivedDailySummarySerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = ArchivedDailySummary
        fields = [
            'id', 'date', 'user', 'user_name', 'total_requests', 'total_sales',
            'total_expenses', 'total_profit', 'total_damages', 'total_returns',
            'total_bonus', 'data'
        ]
        read_only_fields = [
            'date', 'user', 'total_requests', 'total_sales',
            'total_expenses', 'total_profit', 'total_damages', 'total_returns',
            'total_bonus', 'data'
        ]

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"


class InventorySummarySerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = InventorySummary
        fields = [
            'id', 'user', 'user_name', 'date', 'total_quantity', 'total_sold',
            'total_damaged', 'total_bonus', 'total_returned', 'total_remaining',
            'total_value', 'total_sold_value', 'total_damaged_value',
            'total_bonus_value', 'total_remaining_value', 'data'
        ]
        read_only_fields = [
            'user', 'date', 'total_quantity', 'total_sold',
            'total_damaged', 'total_bonus', 'total_returned', 'total_remaining',
            'total_value', 'total_sold_value', 'total_damaged_value',
            'total_bonus_value', 'total_remaining_value', 'data'
        ]

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"


class PartnerProductFinanceSerializer(serializers.Serializer):
    """Сериализатор для работы с финансами отдельного товара партнера"""
    partner_product_id = serializers.IntegerField()
    entry_type = serializers.ChoiceField(choices=FinanceEntry.ENTRY_TYPE_CHOICES)
    quantity = serializers.IntegerField(min_value=1)
    note = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        partner_product_id = data.get('partner_product_id')
        entry_type = data.get('entry_type')
        quantity = data.get('quantity')
        user = self.context.get('request').user

        try:
            partner_product = PartnerProduct.objects.get(id=partner_product_id)

            # Проверка, что партнер имеет доступ к выбранному товару
            if partner_product.partner.id != user.id and not user.is_staff:
                raise serializers.ValidationError(
                    {"partner_product_id": "Вы можете выбрать только товары из вашего личного каталога"}
                )

            # Проверки в зависимости от типа записи
            if entry_type in ['sale', 'damage']:
                if quantity > partner_product.remaining_quantity:
                    raise serializers.ValidationError(
                        {"quantity": f"Недостаточно товара. Доступно: {partner_product.remaining_quantity}"}
                    )
            elif entry_type == 'return':
                if quantity > partner_product.sold_quantity:
                    raise serializers.ValidationError(
                        {
                            "quantity": f"Возврат не может превышать проданное количество ({partner_product.sold_quantity})"}
                    )

        except PartnerProduct.DoesNotExist:
            raise serializers.ValidationError(
                {"partner_product_id": "Указанный товар не найден"}
            )

        return data