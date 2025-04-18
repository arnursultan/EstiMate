from rest_framework import serializers
from .models import Order, OrderItem, DefectItem
from apps.products.models import Product, PartnerInventory
from apps.stores.models import Store, StoreDebt, StoreDebtPayment, StoreExpense
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


# Исправляем валидацию в OrderItemSerializer
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
        user = request.user if request else None

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
            elif order.order_type == 'partner_to_store' and user:
                # Строгая проверка наличия товара в инвентаре партнера
                try:
                    inventory = PartnerInventory.objects.get(partner=user, product=product)
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
    partner_email = serializers.SerializerMethodField()
    partner_phone = serializers.SerializerMethodField()
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
            'partner', 'partner_name', 'partner_email', 'partner_phone',
            'status', 'order_type', 'is_group_order', 'created_at', 'updated_at',
            'total_price', 'total_items', 'total_bonus_items',
            'total_defect_items', 'total_defect_price',
            'order_items', 'defect_items'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def get_partner_name(self, obj):
        return f"{obj.partner.first_name} {obj.partner.last_name}"

    def get_partner_email(self, obj):
        return obj.partner.email if obj.partner else None

    def get_partner_phone(self, obj):
        return obj.partner.phone if obj.partner and hasattr(obj.partner, 'phone') else None

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

                # ИЗМЕНЕНО: Убрана проверка принадлежности магазина партнеру
                # Оставлена только проверка статуса магазина
                store = data.get('store')
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
        if not data.get('is_group_order'):
            items = self.context.get('items', [])
            order_items = self.context['request'].data.get('order_items', [])
            all_items = items or order_items

            if len(all_items) > 1:
                raise serializers.ValidationError("Одиночный заказ может содержать только один товар")

        return data

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class OrderWithItemsSerializer(OrderSerializer):
    items = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False
    )

    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields + ['items']

    @transaction.atomic
    def create(self, validated_data):
        # Извлекаем данные о товарах
        items_data = validated_data.pop('items', [])
        order_items = self.context['request'].data.get('order_items', [])
        if not items_data and order_items:
            items_data = order_items

        if not items_data:
            raise serializers.ValidationError({"error": "Заказ должен содержать хотя бы один товар"})

        user = self.context['request'].user
        order_type = validated_data.get('order_type')

        # Проверяем и обрабатываем товары в зависимости от типа заказа
        if order_type == 'admin_to_partner':
            # Для заказов у администратора используем обычные product_id
            self._validate_admin_to_partner_items(items_data)
        elif order_type == 'partner_to_store':
            # Для заказов магазинам используем inventory_id
            self._validate_partner_to_store_items(items_data, user)

        # Создаем заказ
        order = super().create(validated_data)
        logger.info(f"Создан заказ ID: {order.id}, тип: {order.order_type}")

        # Обрабатываем товары в зависимости от типа заказа
        if order_type == 'admin_to_partner':
            total_order_price = self._process_admin_to_partner_items(order, items_data)
        elif order_type == 'partner_to_store':
            total_order_price = self._process_partner_to_store_items(order, items_data, user)
        else:
            total_order_price = 0

        # Создаем долг магазина
        if order_type == 'partner_to_store' and order.store and total_order_price > 0:
            StoreDebt.objects.create(
                store=order.store,
                amount=total_order_price,
                description=f"Долг за заказ #{order.id} от {timezone.now().strftime('%d.%m.%Y')}",
                is_paid=False
            )

        # Обновляем заказ
        order.refresh_from_db()
        return order

    def _validate_admin_to_partner_items(self, items_data):
        """Проверка товаров для заказа у администратора"""
        valid_items = []
        for item_data in items_data:
            try:
                product_id = self._get_product_id(item_data)
                if not product_id:
                    raise serializers.ValidationError({"error": "ID товара не указан"})

                quantity = int(item_data.get('quantity', 0))
                if quantity <= 0:
                    raise serializers.ValidationError({"error": f"Количество товара должно быть больше нуля"})

                # Проверяем наличие товара в общем каталоге
                product = Product.objects.get(id=product_id)
                if not product.is_active:
                    raise serializers.ValidationError({"error": f"Товар '{product.name}' не активен"})

                if quantity > product.quantity:
                    raise serializers.ValidationError(
                        {"error": f"Недостаточно товара '{product.name}' на складе. Доступно: {product.quantity} шт."}
                    )

                valid_items.append({
                    'product_id': product_id,
                    'quantity': quantity
                })
            except Product.DoesNotExist:
                raise serializers.ValidationError({"error": f"Товар с ID {product_id} не найден"})

        if not valid_items:
            raise serializers.ValidationError({"error": "Нет корректных товаров для заказа"})

        return valid_items

    def _validate_partner_to_store_items(self, items_data, user):
        """Проверка элементов инвентаря для заказа магазину"""
        valid_items = []
        for item_data in items_data:
            try:
                # Ищем ID инвентаря (а не ID товара)
                inventory_id = None
                for field in ['inventory_id', 'id']:
                    if field in item_data and item_data[field]:
                        inventory_id = item_data[field]
                        break

                if not inventory_id:
                    raise serializers.ValidationError({"error": "ID элемента инвентаря не указан"})

                quantity = int(item_data.get('quantity', 0))
                if quantity <= 0:
                    raise serializers.ValidationError({"error": f"Количество товара должно быть больше нуля"})

                # Проверяем наличие элемента в инвентаре партнера
                inventory_item = PartnerInventory.objects.get(id=inventory_id, partner=user)

                if quantity > inventory_item.quantity:
                    raise serializers.ValidationError(
                        {
                            "error": f"Недостаточно товара '{inventory_item.product.name}' в вашем инвентаре. Доступно: {inventory_item.quantity} шт."}
                    )

                valid_items.append({
                    'inventory_id': inventory_id,
                    'quantity': quantity
                })
            except PartnerInventory.DoesNotExist:
                raise serializers.ValidationError(
                    {"error": f"Элемент инвентаря с ID {inventory_id} не найден в вашем инвентаре"})

        if not valid_items:
            raise serializers.ValidationError({"error": "Нет корректных товаров для заказа"})

        return valid_items

    def _process_admin_to_partner_items(self, order, items_data):
        """Обработка товаров для заказа у администратора"""
        total_price = 0
        any_item_created = False

        for item_data in items_data:
            try:
                product_id = self._get_product_id(item_data)
                quantity = int(item_data.get('quantity', 0))

                product = Product.objects.get(id=product_id)

                # Уменьшаем количество товара у администратора
                if product.quantity >= quantity:
                    product.quantity -= quantity
                    product.save()

                    # Создаем элемент заказа
                    order_item = OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=quantity,
                        price=product.price
                    )

                    total_price += float(order_item.total_price)
                    any_item_created = True
                else:
                    raise serializers.ValidationError(
                        {"error": f"Недостаточно товара '{product.name}' на складе. Доступно: {product.quantity} шт."}
                    )
            except Product.DoesNotExist:
                raise serializers.ValidationError({"error": f"Товар с ID {product_id} не найден"})

        if not any_item_created:
            transaction.set_rollback(True)
            raise serializers.ValidationError({"error": "Не удалось создать ни один элемент заказа"})

        return total_price

    def _process_partner_to_store_items(self, order, items_data, user):
        """Обработка товаров для заказа магазину из инвентаря партнера"""
        total_price = 0
        any_item_created = False

        for item_data in items_data:
            try:
                # Получаем ID инвентаря (а не ID товара)
                inventory_id = None
                for field in ['inventory_id', 'id']:
                    if field in item_data and item_data[field]:
                        inventory_id = item_data[field]
                        break

                quantity = int(item_data.get('quantity', 0))

                # Получаем элемент инвентаря и связанный продукт
                inventory_item = PartnerInventory.objects.select_for_update().get(id=inventory_id, partner=user)
                product = inventory_item.product

                # Проверяем наличие нужного количества
                if inventory_item.quantity >= quantity:
                    # Создаем элемент заказа
                    order_item = OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=quantity,
                        price=product.price
                    )

                    # Уменьшаем количество в инвентаре
                    inventory_item.quantity -= quantity
                    inventory_item.save()

                    total_price += float(order_item.total_price)
                    any_item_created = True

                    logger.info(
                        f"Создан элемент заказа ID: {order_item.id}, товар: {product.name}, количество: {quantity}")
                    logger.info(
                        f"Обновлен инвентарь партнера ID: {inventory_id}, товар: {product.name}, новое количество: {inventory_item.quantity}")
                else:
                    raise serializers.ValidationError(
                        {
                            "error": f"Недостаточно товара '{product.name}' в вашем инвентаре. Доступно: {inventory_item.quantity} шт."}
                    )
            except PartnerInventory.DoesNotExist:
                raise serializers.ValidationError(
                    {"error": f"Элемент инвентаря с ID {inventory_id} не найден в вашем инвентаре"})

        if not any_item_created:
            transaction.set_rollback(True)
            raise serializers.ValidationError({"error": "Не удалось создать ни один элемент заказа"})

        return total_price

    def _get_product_id(self, item_data):
        """Получает ID товара из данных элемента заказа"""
        for field in ['product_id', 'product', 'id']:
            if field in item_data and item_data[field]:
                return item_data[field]
        return None


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

        # Изменено: убрана проверка принадлежности заказа текущему пользователю
        # Теперь любой партнер может регистрировать брак для любого заказа
        user = self.context['request'].user
        if user.role != 'admin' and user.role != 'partner':
            raise serializers.ValidationError("Только администраторы и партнеры могут регистрировать брак")

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
                logger.error(f"Ошибка при добавлении бракованного товара: {str(e)}")
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

        # Удалена проверка принадлежности магазина текущему пользователю
        # Теперь любой партнер может оплачивать долги любого магазина

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

        # Удалена проверка принадлежности магазина пользователю
        # Теперь любой партнер может добавлять расходы для любого магазина

        return data


# В файле apps/products/serializers.py добавить новый сериализатор

class PartnerInventoryDetailSerializer(serializers.ModelSerializer):
    """Расширенный сериализатор для отображения инвентаря партнера с подробной информацией о товарах"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_description = serializers.CharField(source='product.description', read_only=True)
    product_price = serializers.DecimalField(
        source='product.price',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    is_bonus = serializers.BooleanField(source='product.is_bonus', read_only=True)
    product_image = serializers.SerializerMethodField()
    available_quantity = serializers.IntegerField(source='quantity', read_only=True)

    class Meta:
        model = PartnerInventory
        fields = [
            'id', 'product', 'product_name', 'product_description',
            'product_price', 'is_bonus', 'available_quantity',
            'product_image', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'partner']

    def get_product_image(self, obj):
        request = self.context.get('request')
        if obj.product.image and request:
            return request.build_absolute_uri(obj.product.image.url)
        return None