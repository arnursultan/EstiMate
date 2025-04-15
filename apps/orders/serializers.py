from rest_framework import serializers
from .models import Order, OrderItem, DefectItem
from apps.products.models import Product, PartnerInventory
from apps.stores.models import Store, StoreDebt, StoreDebtPayment, StoreExpense
from django.db import transaction
from django.utils import timezone


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_price = serializers.DecimalField(source='product.price', max_digits=10, decimal_places=2, read_only=True)
    total_price = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = OrderItem
        fields = [
            'id', 'order', 'product', 'product_name', 'product_price',
            'quantity', 'price', 'total_price', 'bonus_quantity', 'created_at'
        ]
        read_only_fields = ['order', 'price', 'bonus_quantity', 'created_at']

    def validate(self, data):
        request = self.context.get('request')
        product = data.get('product')
        quantity = data.get('quantity', 0)

        if not product:
            raise serializers.ValidationError("Необходимо указать товар")

        if quantity <= 0:
            raise serializers.ValidationError("Количество должно быть больше нуля")

        # Проверка доступности товара
        if not product.is_active:
            raise serializers.ValidationError(f"Товар '{product.name}' не активен")

        # Проверки в зависимости от типа заказа
        order = self.context.get('order')
        if order:
            # Для заказов от партнера к админу
            if order.order_type == 'admin_to_partner':
                # Проверка наличия товара на складе администратора
                if quantity > product.quantity:
                    raise serializers.ValidationError(
                        f"Недостаточно товара '{product.name}' на складе. Доступно: {product.quantity} шт.")

            # Для заказов от партнера к магазину
            elif order.order_type == 'partner_to_store':
                # Проверка наличия товара в инвентаре партнера
                try:
                    inventory = PartnerInventory.objects.get(partner=request.user, product=product)
                    if quantity > inventory.quantity:
                        raise serializers.ValidationError(
                            f"Недостаточно товара '{product.name}' в вашем инвентаре. Доступно: {inventory.quantity} шт.")
                except PartnerInventory.DoesNotExist:
                    raise serializers.ValidationError(f"Товар '{product.name}' отсутствует в вашем инвентаре")

        return data

    def create(self, validated_data):
        order = self.context.get('order')
        product = validated_data.get('product')

        # Установка цены из прайс-листа
        validated_data['price'] = product.price
        validated_data['order'] = order

        return super().create(validated_data)


class DefectItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = DefectItem
        fields = [
            'id', 'order', 'product', 'product_name',
            'quantity', 'description', 'total_price', 'created_at'
        ]
        read_only_fields = ['created_at']

    def validate(self, data):
        order = data.get('order') or self.context.get('order')
        product = data.get('product')
        quantity = data.get('quantity', 0)

        if not order:
            raise serializers.ValidationError("Необходимо указать заказ")

        if not product:
            raise serializers.ValidationError("Необходимо указать товар")

        if quantity <= 0:
            raise serializers.ValidationError("Количество должно быть больше нуля")

        # Проверяем, что заказ имеет тип partner_to_store
        if order.order_type != 'partner_to_store':
            raise serializers.ValidationError("Можно регистрировать брак только для заказов магазину")

        # Проверяем, что заказ подтвержден
        if order.status != 'confirmed':
            raise serializers.ValidationError("Можно регистрировать брак только для подтвержденных заказов")

        # Проверяем, что товар был в заказе
        order_item = OrderItem.objects.filter(order=order, product=product).first()
        if not order_item:
            raise serializers.ValidationError(f"Товар '{product.name}' отсутствует в данном заказе")

        # Проверяем, что количество бракованных товаров не превышает заказанное количество
        if quantity > order_item.quantity:
            raise serializers.ValidationError(
                f"Количество бракованных товаров не может превышать количество заказанных ({order_item.quantity} шт.)")

        return data


class OrderSerializer(serializers.ModelSerializer):
    order_items = OrderItemSerializer(many=True, read_only=True)
    defect_items = DefectItemSerializer(many=True, read_only=True)
    store_name = serializers.CharField(source='store.name', read_only=True)
    partner_name = serializers.SerializerMethodField()
    total_price = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        read_only=True,
    )
    total_items = serializers.SerializerMethodField()
    total_bonus_items = serializers.IntegerField(read_only=True)
    total_defect_items = serializers.SerializerMethodField()
    total_defect_price = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'created_by', 'store', 'store_name',
            'partner', 'partner_name', 'partner_email', 'partner_phone',  # Включаем новые поля
            'status', 'order_type', 'is_group_order', 'created_at', 'updated_at',
            'total_price', 'total_items', 'total_bonus_items',
            'total_defect_items', 'total_defect_price',  # Новые поля для бракованных товаров
            'order_items', 'defect_items'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']


    def get_partner_name(self, obj):
        return f"{obj.partner.first_name} {obj.partner.last_name}"


    def get_total_items(self, obj):
        return sum(item.quantity for item in obj.order_items.all())


    def get_total_defect_items(self, obj):
        """Получение общего количества бракованных товаров"""
        return sum(defect.quantity for defect in obj.defect_items.all())


    def get_total_defect_price(self, obj):
        """Получение общей стоимости бракованных товаров"""
        return sum(defect.total_price for defect in obj.defect_items.all())

    def validate(self, data):
        user = self.context['request'].user

        # Проверки для партнеров
        if user.role == 'partner':
            # Проверка для заказов от партнера к магазину
            if data.get('order_type') == 'partner_to_store':
                if not data.get('store'):
                    raise serializers.ValidationError("Для заказа магазину необходимо указать магазин")

                # Проверка, что магазин принадлежит партнеру
                store = data.get('store')
                if store.partner != user:
                    raise serializers.ValidationError("Вы можете создавать заказы только для своих магазинов")

                # Проверка статуса магазина
                if store.status != 'approved':
                    raise serializers.ValidationError("Магазин должен быть одобрен для создания заказа")

            # Проверка для заказов от партнера к админу
            if data.get('order_type') == 'admin_to_partner':
                # Партнер может указать только себя как получателя
                if data.get('partner') != user:
                    raise serializers.ValidationError("Вы можете создавать заказы только для себя")

        # Проверки для админов
        if user.role == 'admin':
            if data.get('order_type') == 'admin_to_partner':
                # Проверка, что получатель - партнер
                partner = data.get('partner')
                if not partner or partner.role != 'partner':
                    raise serializers.ValidationError("Получателем может быть только партнер")

            elif data.get('order_type') == 'partner_to_store':
                # Админ не может создавать заказы от партнера к магазину
                raise serializers.ValidationError("Администраторы не могут создавать заказы от партнера к магазину")

        # Проверка для одиночного заказа
        if not data.get('is_group_order') and self.context.get('items', []) and len(self.context.get('items', [])) > 1:
            raise serializers.ValidationError("Одиночный заказ может содержать только один товар")

        return data

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class OrderWithItemsSerializer(OrderSerializer):
    items = serializers.ListField(
        child=serializers.DictField(),
        write_only=True
    )

    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields + ['items']

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items', [])

        # Для одиночного заказа проверяем, что есть только один товар
        if not validated_data.get('is_group_order') and len(items_data) > 1:
            raise serializers.ValidationError("Одиночный заказ может содержать только один товар")

        # Создаем заказ
        order = super().create(validated_data)

        # Общая стоимость заказа для создания долга магазина
        total_order_price = 0

        # Добавляем товары к заказу
        for item_data in items_data:
            try:
                product_id = item_data.get('product_id') or item_data.get('product')
                if not product_id:
                    continue

                product = Product.objects.get(id=product_id)
                quantity = int(item_data.get('quantity', 0))

                if product.is_active and quantity > 0:
                    # Создаем элемент заказа
                    order_item = OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=quantity,
                        price=product.price
                    )

                    total_order_price += float(order_item.total_price)

                    # Если заказ от партнера к магазину, уменьшаем количество товара в инвентаре партнера
                    if order.order_type == 'partner_to_store':
                        try:
                            inventory = PartnerInventory.objects.get(
                                partner=order.created_by,
                                product=product
                            )

                            if inventory.quantity >= quantity:
                                inventory.quantity -= quantity
                                inventory.save()
                            else:
                                # Логируем ошибку, если недостаточно товара
                                print(
                                    f"Недостаточно товара {product.name} в инвентаре партнера {order.created_by.email}")
                        except PartnerInventory.DoesNotExist:
                            # Логируем ошибку, если товара нет в инвентаре
                            print(f"Товар {product.name} отсутствует в инвентаре партнера {order.created_by.email}")
            except (Product.DoesNotExist, ValueError, TypeError) as e:
                # Логируем ошибку при обработке товара
                print(f"Ошибка при добавлении товара в заказ: {str(e)}")
                continue

        # Создаем долг магазина, если это заказ от партнера к магазину
        if order.order_type == 'partner_to_store' and order.store and total_order_price > 0:
            StoreDebt.objects.create(
                store=order.store,
                amount=total_order_price,
                description=f"Долг за заказ #{order.id} от {timezone.now().strftime('%d.%m.%Y')}",
                is_paid=False
            )

        return order


class OrderStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['status']

    @transaction.atomic
    def update(self, instance, validated_data):
        old_status = instance.status
        new_status = validated_data.get('status')

        # Проверяем допустимость изменения статуса
        if old_status == 'rejected' and new_status != 'rejected':
            raise serializers.ValidationError("Нельзя изменить статус отклоненного заказа")
        if old_status == 'confirmed' and new_status != 'confirmed':
            raise serializers.ValidationError("Нельзя изменить статус подтвержденного заказа")

        # Обработка различных переходов статусов
        if instance.order_type == 'admin_to_partner':
            # Проверка прав доступа - только администратор может изменять статус заказа партнера к админу
            user = self.context['request'].user
            if user.role != 'admin':
                raise serializers.ValidationError("Только администратор может изменять статус заказа к администратору")

            # Подтверждение заказа
            if new_status == 'confirmed' and old_status == 'in_process':
                self._process_confirmed_admin_to_partner(instance)

            # Отклонение заказа
            elif new_status == 'rejected' and old_status == 'in_process':
                # Для отклонения заказа ничего делать не нужно
                pass

        # Для заказов от партнера к магазину нельзя изменить статус, они автоматически подтверждаются
        elif instance.order_type == 'partner_to_store':
            raise serializers.ValidationError("Статус заказа от партнера к магазину не может быть изменен")

        # Обновляем статус заказа
        instance.status = new_status
        instance.save()

        return instance

    def _process_confirmed_admin_to_partner(self, order):
        """Обработка подтверждения заказа от администратора к партнеру"""
        # Обновляем количество товаров на складе и в инвентаре партнера
        for item in order.order_items.all():
            product = item.product

            # Уменьшаем количество товара на складе администратора
            if product.quantity >= item.quantity:
                product.quantity -= item.quantity
                product.save()

                # Увеличиваем количество товара в инвентаре партнера
                partner_inventory, created = PartnerInventory.objects.get_or_create(
                    partner=order.partner,
                    product=product,
                    defaults={'quantity': 0}
                )
                partner_inventory.quantity += item.quantity
                partner_inventory.save()


class DefectGroupSerializer(serializers.Serializer):
    """Сериализатор для добавления группы бракованных товаров"""
    order_id = serializers.IntegerField(required=False)
    store_id = serializers.IntegerField(required=False)
    date = serializers.DateField(required=False)
    defects = serializers.ListField(
        child=serializers.DictField()
    )

    def validate(self, data):
        # Проверяем, что есть либо order_id, либо (store_id и date)
        if 'order_id' not in data and ('store_id' not in data or 'date' not in data):
            raise serializers.ValidationError(
                "Необходимо указать либо order_id, либо store_id и date"
            )

        return data

    @transaction.atomic
    def create(self, validated_data):
        order_id = validated_data.get('order_id')
        store_id = validated_data.get('store_id')
        date = validated_data.get('date')
        defects_data = validated_data.get('defects', [])

        # Если указаны store_id и date, находим последний заказ
        if not order_id and store_id and date:
            try:
                # Найти последний заказ для магазина на указанную дату
                orders = Order.objects.filter(
                    store_id=store_id,
                    created_at__date=date,
                    order_type='partner_to_store',
                    status='confirmed'
                ).order_by('-created_at')

                if orders.exists():
                    order_id = orders.first().id
                else:
                    raise serializers.ValidationError(
                        f"Заказы для магазина ID:{store_id} на дату {date} не найдены"
                    )
            except Exception as e:
                raise serializers.ValidationError(f"Ошибка поиска заказа: {str(e)}")

        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            raise serializers.ValidationError("Заказ не найден")

        # Проверяем, что заказ от партнера к магазину
        if order.order_type != 'partner_to_store':
            raise serializers.ValidationError("Можно регистрировать брак только для заказов магазину")

        # Проверяем, что заказ подтвержден
        if order.status != 'confirmed':
            raise serializers.ValidationError("Можно регистрировать брак только для подтвержденных заказов")

        # Проверяем, что пользователь имеет право добавлять брак
        user = self.context['request'].user
        if user.role != 'admin' and order.created_by != user:
            raise serializers.ValidationError("Вы не можете регистрировать брак для этого заказа")

        created_defects = []

        for defect_data in defects_data:
            try:
                product_id = defect_data.get('product_id')
                quantity = int(defect_data.get('quantity', 0))
                description = defect_data.get('description', '')

                product = Product.objects.get(id=product_id)

                # Проверяем, что товар был в заказе
                order_item = OrderItem.objects.filter(order=order, product=product).first()
                if not order_item:
                    continue

                # Проверяем, что количество бракованных товаров не превышает заказанное количество
                if quantity <= 0 or quantity > order_item.quantity:
                    continue

                # Создаем запись о бракованном товаре
                defect = DefectItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    description=description
                )

                created_defects.append(defect)

            except (Product.DoesNotExist, ValueError, TypeError, KeyError) as e:
                print(f"Ошибка при добавлении бракованного товара: {str(e)}")
                continue

        return created_defects


class StoreDebtPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreDebtPayment
        fields = ['id', 'store', 'amount', 'description', 'payment_date']
        read_only_fields = ['payment_date']

    def validate(self, data):
        store = data.get('store')
        amount = data.get('amount')

        if not store:
            raise serializers.ValidationError("Необходимо указать магазин")

        if not amount or amount <= 0:
            raise serializers.ValidationError("Сумма оплаты должна быть больше нуля")

        # Проверяем, что у магазина есть неоплаченный долг
        remaining_debt = store.remaining_debt
        if remaining_debt <= 0:
            raise serializers.ValidationError("У магазина нет неоплаченного долга")

        # Проверяем, что сумма оплаты не превышает оставшийся долг
        if amount > remaining_debt:
            raise serializers.ValidationError(f"Сумма оплаты превышает оставшийся долг ({remaining_debt} сом)")

        return data


class StoreExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreExpense
        fields = ['id', 'store', 'amount', 'description', 'expense_date', 'created_at']
        read_only_fields = ['created_at']

    def validate(self, data):
        store = data.get('store')
        amount = data.get('amount')

        if not store:
            raise serializers.ValidationError("Необходимо указать магазин")

        if not amount or amount <= 0:
            raise serializers.ValidationError("Сумма расхода должна быть больше нуля")

        # Проверяем, что пользователь имеет доступ к магазину
        user = self.context['request'].user
        if user.role != 'admin' and store.partner != user:
            raise serializers.ValidationError("У вас нет доступа к этому магазину")

        return data