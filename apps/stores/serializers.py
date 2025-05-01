from rest_framework import serializers
from django.utils import timezone
from .models import City, Store, StoreDebt, StoreDebtPayment # Убрали StoreExpense
from decimal import Decimal # Импорт Decimal

class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ['id', 'name']


class StoreSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)
    partner_name = serializers.SerializerMethodField()
    total_debt = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        read_only=True, coerce_to_string=False # Важно для чисел с плавающей точкой
    )
    total_paid_debt = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        read_only=True, coerce_to_string=False
    )
    remaining_debt = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        read_only=True, coerce_to_string=False
    )

    class Meta:
        model = Store
        fields = [
            'id', 'name', 'inn', 'phone', 'city', 'city_name',
            'address', # Убрали 'expenses'
            'partner', 'partner_name',
            'status', 'is_active', 'is_deleted', 'created_at', 'updated_at', 'total_debt',
            'total_paid_debt', 'remaining_debt'
        ]
        # Убрали expenses из read_only_fields
        read_only_fields = [
            'created_at', 'updated_at', 'partner', 'total_debt',
            'total_paid_debt', 'remaining_debt', 'is_deleted'
            ]

    def get_partner_name(self, obj):
        return f"{obj.partner.first_name} {obj.partner.last_name}" if obj.partner else None

    def validate(self, data):
        # Проверка ИНН
        inn = data.get('inn')
        if inn and len(inn) < 10: # Оставляем базовую проверку
            raise serializers.ValidationError({"inn": "ИНН должен содержать не менее 10 цифр"})

        # Проверка телефона
        phone = data.get('phone')
        if phone and not phone.startswith('+'): # Оставляем базовую проверку
             raise serializers.ValidationError({"phone": "Номер телефона должен начинаться с +"})

        # Проверка имени магазина - первая буква заглавная
        name = data.get('name')
        if name:
            name = name.strip()
            if name:
                 data['name'] = name[0].upper() + name[1:] # Форматируем здесь при создании/обновлении

        # Статус по умолчанию устанавливается в модели или view
        # data['status'] = 'approved'
        # data['is_deleted'] = False

        return data

    def create(self, validated_data):
        # Устанавливаем партнера и статус при создании через API
        user = self.context['request'].user
        validated_data['partner'] = user
        # Устанавливаем статус 'approved' и is_deleted=False по умолчанию при создании через API
        validated_data['status'] = 'approved'
        validated_data['is_deleted'] = False
        return super().create(validated_data)


class StoreListSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)
    partner_name = serializers.SerializerMethodField()
    remaining_debt = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        read_only=True, coerce_to_string=False
    )

    class Meta:
        model = Store
        fields = [
            'id', 'name', 'city_name', 'partner', 'partner_name',
            'status', 'remaining_debt', 'is_active', 'is_deleted',
            'inn', 'phone'
        ]

    def get_partner_name(self, obj):
        return f"{obj.partner.first_name} {obj.partner.last_name}" if obj.partner else None


class StoreDebtSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.name', read_only=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'), coerce_to_string=False)

    class Meta:
        model = StoreDebt
        fields = [
            'id', 'store', 'store_name', 'amount', 'description',
            'is_paid', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    # Убираем validate, т.к. min_value уже в поле
    # def validate(self, data): ...

# --- НОВЫЙ СЕРИАЛИЗАТОР ---
class StoreDebtPaymentSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.name', read_only=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'), coerce_to_string=False)

    class Meta:
        model = StoreDebtPayment
        fields = ['id', 'store', 'store_name', 'amount', 'description', 'payment_date']
        read_only_fields = ['payment_date']

    def validate(self, data):
        store = data.get('store')
        amount = data.get('amount')
        request = self.context.get('request')

        if not store:
            # Пытаемся получить магазин из контекста URL, если не передан в data
            view = self.context.get('view')
            if view and hasattr(view, 'kwargs'):
                 store_id = view.kwargs.get('store_pk') or view.kwargs.get('pk')
                 if store_id:
                     try:
                         store = Store.objects.get(id=store_id)
                         data['store'] = store
                     except Store.DoesNotExist:
                         raise serializers.ValidationError({"store": "Магазин не найден."})
                 else:
                     raise serializers.ValidationError({"store": "Необходимо указать магазин."})
            else:
                 raise serializers.ValidationError({"store": "Необходимо указать магазин."})

        if not amount: # Проверка на None и 0
             raise serializers.ValidationError({"amount": "Сумма оплаты должна быть больше нуля"})

        # Проверяем, что у магазина есть долг
        remaining_debt = store.remaining_debt
        if remaining_debt <= Decimal('0.00'):
            raise serializers.ValidationError({"detail": "У магазина нет неоплаченного долга"})

        # Проверяем, что сумма оплаты не превышает оставшийся долг
        if amount > remaining_debt:
            raise serializers.ValidationError(f"Сумма оплаты ({amount}) превышает оставшийся долг ({remaining_debt} сом)")

        # Проверка прав доступа пользователя (админ или владелец магазина)
        if request and not (request.user.role == 'admin' or (request.user.role == 'partner' and store.partner == request.user)):
             raise serializers.ValidationError("У вас нет прав для добавления оплаты этому магазину")

        return data
