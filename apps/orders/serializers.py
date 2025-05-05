# apps/orders/serializers.py
from rest_framework import serializers, exceptions
from .models import Order, OrderItem, DefectItem
from apps.products.models import Product, PartnerInventory
from apps.stores.models import Store, StoreDebt, StoreDebtPayment
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import logging
from apps.stores.serializers import StoreDebtPaymentSerializer
from apps.products.serializers import PartnerInventoryDetailSerializer
from apps.users.models import User
from rest_framework.exceptions import PermissionDenied # Убедись, что импортирован
from django.db.models import Sum


logger = logging.getLogger(__name__)

# --- OrderItemSerializer ---
# (без изменений, как в предыдущем ответе)
class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_price = serializers.DecimalField(source='product.price', max_digits=10, decimal_places=2, read_only=True, coerce_to_string=False)
    total_price = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        read_only=True, coerce_to_string=False
    )
    quantity = serializers.IntegerField(min_value=1) # Минимум 1
    product = serializers.PrimaryKeyRelatedField(
         queryset=Product.objects.filter(is_deleted=False) # Разрешаем заказывать неактивные, но не удаленные
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
        quantity = data.get('quantity') # min_value=1 уже проверено
        user = request.user if request else None

        if not product:
            raise serializers.ValidationError({"product": "Необходимо указать товар"})

        instance = self.instance
        order = self.context.get('order')

        if not instance and order and user: # Проверяем наличие только при создании элемента заказа
            if order.order_type == 'admin_to_partner':
                # Проверяем остаток на складе админа
                if quantity > product.quantity:
                    raise serializers.ValidationError(
                        {"quantity": f"Недостаточно товара '{product.name}' на складе администратора. Доступно: {product.quantity} шт."}
                    )
            elif order.order_type == 'partner_to_store':
                # Проверяем остаток в инвентаре партнера (создателя заказа)
                try:
                    # Важно: проверяем инвентарь создателя заказа (order.created_by)
                    inventory = PartnerInventory.objects.get(partner=order.created_by, product=product)
                    if quantity > inventory.quantity:
                        raise serializers.ValidationError(
                             {"quantity": f"Недостаточно товара '{product.name}' в инвентаре создателя заказа. Доступно: {inventory.quantity} шт."}
                         )
                except PartnerInventory.DoesNotExist:
                    raise serializers.ValidationError(f"Товар '{product.name}' отсутствует в инвентаре создателя заказа.")

        return data

    def create(self, validated_data):
        order = self.context.get('order')
        product = validated_data.get('product')
        validated_data['price'] = product.price # Цена берется из товара на момент создания
        validated_data['order'] = order
        # Бонусы будут рассчитаны в OrderItem.save()
        return super().create(validated_data)


# --- DefectItemSerializer ---
# (без изменений, как в предыдущем ответе)
class DefectItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, coerce_to_string=False)
    quantity = serializers.IntegerField(min_value=1)
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())

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
        quantity = data.get('quantity')

        if not order:
            raise serializers.ValidationError("Необходимо указать заказ")
        if not product:
            raise serializers.ValidationError("Необходимо указать товар")

        if order.order_type != 'partner_to_store':
            raise serializers.ValidationError("Брак можно регистрировать только для заказов магазину")
        if order.status != 'confirmed':
            raise serializers.ValidationError("Брак можно регистрировать только для подтвержденных заказов")

        # Удалена проверка роли - все могут добавлять брак

        order_item = OrderItem.objects.filter(order=order, product=product).first()
        if not order_item:
            raise serializers.ValidationError(f"Товар '{product.name}' отсутствует в данном заказе")

        if quantity > order_item.quantity:
            raise serializers.ValidationError(
                f"Количество брака не может превышать заказанное ({order_item.quantity} шт.)")

        return data

# --- OrderSerializer ---
# (без изменений, как в предыдущем ответе)
class OrderSerializer(serializers.ModelSerializer):
    order_items = OrderItemSerializer(many=True, read_only=True)
    defect_items = DefectItemSerializer(many=True, read_only=True)
    store_name = serializers.CharField(source='store.name', read_only=True, allow_null=True)
    partner_name = serializers.SerializerMethodField()
    partner_email = serializers.SerializerMethodField()
    partner_phone = serializers.SerializerMethodField()
    total_price = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        read_only=True, coerce_to_string=False
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
        read_only_fields = ['created_by', 'created_at', 'updated_at', 'status']

    def get_partner_name(self, obj):
        return f"{obj.partner.first_name} {obj.partner.last_name}" if obj.partner else None

    def get_partner_email(self, obj):
        return obj.partner.email if obj.partner else None

    def get_partner_phone(self, obj):
        return obj.partner.phone if obj.partner and hasattr(obj.partner, 'phone') else None

    def get_total_items(self, obj):
        return obj.order_items.aggregate(total=Sum('quantity'))['total'] or 0

    def get_total_defect_items(self, obj):
        return obj.defect_items.aggregate(total=Sum('quantity'))['total'] or 0

    def get_total_defect_price(self, obj):
        total = Decimal('0.00')
        for item in obj.defect_items.all():
             try:
                  total += item.total_price
             except:
                  pass
        return total

    def validate(self, data):
        # Валидация общих полей, не зависящая от создания
        return data


# --- OrderWithItemsSerializer ---
class OrderWithItemsSerializer(OrderSerializer):
    """Сериализатор для создания заказа с товарами."""
    items = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=True
    )
    store = serializers.PrimaryKeyRelatedField(
        queryset=Store.objects.filter(is_active=True, is_deleted=False, status='approved'),
        required=False,
        allow_null=True
    )
    partner = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True, is_deleted=False, role='partner'),
        required=True
    )
    order_type = serializers.ChoiceField(choices=Order.ORDER_TYPE, required=True)
    is_group_order = serializers.BooleanField(default=True)

    class Meta(OrderSerializer.Meta):
        fields = [
             'id', 'store', 'partner', 'order_type', 'is_group_order', # Поля для создания
             'created_by', 'store_name', 'partner_name', 'partner_email', 'partner_phone', # Read-only
             'status', 'created_at', 'updated_at', # Read-only
             'total_price', 'total_items', 'total_bonus_items', # Read-only
             'total_defect_items', 'total_defect_price', # Read-only
             'order_items', 'defect_items', # Read-only
             'items' # Write-only
        ]
        read_only_fields = [
             'id', 'created_by', 'store_name', 'partner_name', 'partner_email', 'partner_phone',
             'status', 'created_at', 'updated_at',
             'total_price', 'total_items', 'total_bonus_items',
             'total_defect_items', 'total_defect_price',
             'order_items', 'defect_items'
             ]

    # --- ДОБАВЛЯЕМ НЕДОСТАЮЩИЕ МЕТОДЫ ВАЛИДАЦИИ ---
    def _validate_and_get_product(self, item_data):
        """Валидирует ID товара и возвращает объект Product."""
        # Ищет ID в разных возможных ключах
        product_id = item_data.get('product') or item_data.get('product_id') or item_data.get('id')
        if not product_id:
            # Используем raise ValidationError, чтобы DRF правильно обработал ошибку
            raise serializers.ValidationError(f"Не указан ID товара (ожидался ключ 'product' или 'product_id') в элементе: {item_data}")
        try:
            # Конвертируем ID в int на всякий случай
            product_id_int = int(product_id)
        except (ValueError, TypeError):
             raise serializers.ValidationError(f"Некорректный ID товара '{product_id}' в элементе: {item_data}. Ожидалось целое число.")

        try:
            # Проверяем только неудаленные товары
            product = Product.objects.get(id=product_id_int, is_deleted=False)
            # Можно добавить проверку активности здесь, если нужно запретить заказ неактивных
            # if not product.is_active:
            #     raise serializers.ValidationError(f"Товар '{product.name}' (ID: {product_id_int}) не активен.")
            return product
        except Product.DoesNotExist:
            raise serializers.ValidationError(f"Товар с ID {product_id_int} не найден или удален.")

    def _validate_and_get_inventory(self, item_data, user):
         """Валидирует ID инвентаря и возвращает объект PartnerInventory."""
         # Ищет ID в разных возможных ключах
         inventory_id = item_data.get('inventory_id') or item_data.get('id')
         if not inventory_id:
              raise serializers.ValidationError(f"Не указан ID элемента инвентаря (ожидался ключ 'inventory_id') в элементе: {item_data}")
         try:
             inventory_id_int = int(inventory_id)
         except (ValueError, TypeError):
              raise serializers.ValidationError(f"Некорректный ID инвентаря '{inventory_id}' в элементе: {item_data}. Ожидалось целое число.")

         try:
              # Ищем запись инвентаря для КОНКРЕТНОГО партнера (user)
              inventory_item = PartnerInventory.objects.select_related('product').get(id=inventory_id_int, partner=user)
              # Проверяем связанный товар
              if inventory_item.product.is_deleted:
                  raise serializers.ValidationError(f"Товар '{inventory_item.product.name}' (ID: {inventory_item.product.id}), связанный с инвентарем ID {inventory_id_int}, удален.")
              # Можно добавить проверку активности товара
              # if not inventory_item.product.is_active:
              #      raise serializers.ValidationError(f"Товар '{inventory_item.product.name}' (ID: {inventory_item.product.id}), связанный с инвентарем ID {inventory_id_int}, не активен.")
              return inventory_item
         except PartnerInventory.DoesNotExist:
              raise serializers.ValidationError(f"Элемент инвентаря с ID {inventory_id_int} не найден для партнера {user.id}.")
    # --- КОНЕЦ ДОБАВЛЕНИЯ МЕТОДОВ ---

    def validate(self, data):
        # ... (код валидации остается как был в предыдущем ответе) ...
        user = self.context['request'].user
        order_type = data.get('order_type')
        partner = data.get('partner')
        store = data.get('store')
        items = data.get('items')

        if not items:
            raise serializers.ValidationError({"items": "Заказ должен содержать хотя бы один товар"})

        if order_type == 'admin_to_partner':
            if user.role != 'partner':
                 raise PermissionDenied("Только партнер может создавать заказ у администратора.")
            if partner != user:
                 raise serializers.ValidationError({"partner": "Вы можете создать заказ только для себя."})
            if store is not None:
                 raise serializers.ValidationError({"store": "Заказ админу не должен иметь магазин."})

        elif order_type == 'partner_to_store':
            if user.role != 'partner':
                 raise PermissionDenied("Только партнер может создавать заказ для магазина.")
            if partner != user:
                 raise serializers.ValidationError({"partner": "Партнер-получатель должен совпадать с создателем заказа."})
            if not store:
                 raise serializers.ValidationError({"store": "Необходимо указать магазин-получатель."})
        else:
             raise serializers.ValidationError({"order_type": "Некорректный тип заказа."})

        if not data.get('is_group_order', True) and len(items) > 1:
            raise serializers.ValidationError({"is_group_order": "Одиночный заказ может содержать только один товар"})

        return data


    @transaction.atomic
    def create(self, validated_data):
        # ... (код создания заказа и долга остается как был) ...
        items_data = validated_data.pop('items')
        user = self.context['request'].user
        order_type = validated_data.get('order_type')

        validated_data['created_by'] = user

        if order_type == 'partner_to_store':
            validated_data['status'] = 'confirmed'

        order = Order.objects.create(**validated_data)
        logger.info(f"Создан объект заказа ID: {order.id}, тип: {order.order_type}, статус: {order.status}")

        item_serializer_context = {'order': order, 'request': self.context['request']}

        total_order_price = Decimal('0.00')
        try:
            if order_type == 'admin_to_partner':
                total_order_price = self._process_admin_to_partner_items(order, items_data, item_serializer_context)
            elif order_type == 'partner_to_store':
                total_order_price = self._process_partner_to_store_items(order, items_data, user, item_serializer_context)

        except Exception as e:
             logger.error(f"Ошибка при обработке товаров для заказа {order.id}: {e}. Откат транзакции.")
             raise

        if order_type == 'partner_to_store' and order.store and total_order_price > Decimal('0.00'):
            StoreDebt.objects.create(
                store=order.store,
                amount=total_order_price,
                description=f"Долг за заказ #{order.id} от {timezone.now().strftime('%d.%m.%Y')}",
                is_paid=False
            )
            logger.info(f"Создан долг {total_order_price} для магазина {order.store.id} по заказу {order.id}")

        order.refresh_from_db()
        return order


    def _process_admin_to_partner_items(self, order, items_data, item_context):
        # ... (код как в предыдущем ответе, но теперь вызывает self._validate_and_get_product) ...
        total_price = Decimal('0.00')
        products_to_update = {}
        any_item_processed = False

        for item_data in items_data:
            if not isinstance(item_data, dict):
                logger.error(f"Некорректный формат элемента в items для заказа {order.id}: {item_data}")
                continue

            quantity = item_data.get('quantity')
            if not isinstance(quantity, int) or quantity <= 0:
                 logger.warning(f"Некорректное количество в элементе items для заказа {order.id}: {item_data}")
                 continue

            try:
                # --- Используем метод класса ---
                product = self._validate_and_get_product(item_data)
                # ---

                if product.quantity < quantity:
                    raise serializers.ValidationError(
                        f"Недостаточно товара '{product.name}' (ID: {product.id}) на складе администратора. Доступно: {product.quantity}, запрошено: {quantity}"
                    )

                products_to_update[product.id] = products_to_update.get(product.id, 0) + quantity

                item_serializer = OrderItemSerializer(data={'product': product.id, 'quantity': quantity}, context=item_context)
                item_serializer.is_valid(raise_exception=True)
                order_item = item_serializer.save()
                total_price += order_item.total_price
                any_item_processed = True

            except serializers.ValidationError as e:
                 logger.warning(f"Ошибка валидации элемента для заказа {order.id}: {e.detail}. Элемент: {item_data}")
                 raise e
            except Exception as e:
                 logger.exception(f"Ошибка обработки элемента {item_data} для заказа {order.id}: {e}")
                 raise serializers.ValidationError({"items": f"Ошибка обработки товара ID {item_data.get('product', 'N/A')}: {e}"})

        if not any_item_processed:
             raise serializers.ValidationError({"items": "Не удалось обработать ни один товар из списка. Проверьте формат данных и ID товаров."})

        if products_to_update:
             with transaction.atomic():
                 products = Product.objects.select_for_update().filter(id__in=products_to_update.keys())
                 product_map = {p.id: p for p in products}
                 updates = []
                 for product_id, quantity_to_deduct in products_to_update.items():
                      product = product_map.get(product_id)
                      if product and product.quantity >= quantity_to_deduct:
                            product.quantity -= quantity_to_deduct
                            updates.append(product)
                      else:
                           raise serializers.ValidationError(f"Недостаточно товара '{product.name if product else product_id}' при финальном обновлении.")
                 if updates:
                      Product.objects.bulk_update(updates, ['quantity'])
                      logger.info(f"Обновлены остатки для {len(updates)} товаров админа по заказу {order.id}")

        return total_price


    def _process_partner_to_store_items(self, order, items_data, user, item_context):
        # ... (аналогично, но использует self._validate_and_get_inventory) ...
        total_price = Decimal('0.00')
        inventory_to_update = {}
        any_item_processed = False

        for item_data in items_data:
             if not isinstance(item_data, dict):
                 logger.error(f"Некорректный формат элемента в items для заказа {order.id}: {item_data}")
                 continue

             quantity = item_data.get('quantity')
             if not isinstance(quantity, int) or quantity <= 0:
                  logger.warning(f"Некорректное количество в элементе items для заказа {order.id}: {item_data}")
                  continue

             try:
                 # --- Используем метод класса ---
                 inventory_item = self._validate_and_get_inventory(item_data, user)
                 # ---
                 product = inventory_item.product

                 if inventory_item.quantity < quantity:
                      raise serializers.ValidationError(
                           f"Недостаточно товара '{product.name}' (ID: {product.id}) в вашем инвентаре. Доступно: {inventory_item.quantity}, запрошено: {quantity}"
                       )

                 inventory_to_update[inventory_item.id] = inventory_to_update.get(inventory_item.id, 0) + quantity

                 item_serializer = OrderItemSerializer(data={'product': product.id, 'quantity': quantity}, context=item_context)
                 item_serializer.is_valid(raise_exception=True)
                 order_item = item_serializer.save()
                 total_price += order_item.total_price
                 any_item_processed = True

             except serializers.ValidationError as e:
                  logger.warning(f"Ошибка валидации элемента для заказа {order.id}: {e.detail}. Элемент: {item_data}")
                  raise e
             except Exception as e:
                  logger.exception(f"Ошибка обработки элемента {item_data} для заказа {order.id}: {e}")
                  raise serializers.ValidationError({"items": f"Ошибка обработки элемента инвентаря ID {item_data.get('inventory_id', 'N/A')}: {e}"})


        if not any_item_processed:
             raise serializers.ValidationError({"items": "Не удалось обработать ни один товар из списка. Проверьте формат данных и ID инвентаря."})

        if inventory_to_update:
             with transaction.atomic():
                 inventory_items = PartnerInventory.objects.select_for_update().filter(
                     id__in=inventory_to_update.keys(), partner=user
                 )
                 inventory_map = {i.id: i for i in inventory_items}
                 updates = []
                 for inv_id, quantity_to_deduct in inventory_to_update.items():
                     inventory = inventory_map.get(inv_id)
                     if inventory and inventory.quantity >= quantity_to_deduct:
                         inventory.quantity -= quantity_to_deduct
                         updates.append(inventory)
                     else:
                          raise serializers.ValidationError(f"Недостаточно товара '{inventory.product.name if inventory else inv_id}' в инвентаре при финальном обновлении.")
                 if updates:
                      PartnerInventory.objects.bulk_update(updates, ['quantity'])
                      logger.info(f"Обновлены остатки для {len(updates)} позиций инвентаря партнера {user.id} по заказу {order.id}")

        return total_price


# --- OrderStatusUpdateSerializer ---
class OrderStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['status']

    @transaction.atomic
    def update(self, instance, validated_data):
        old_status = instance.status
        new_status = validated_data.get('status')
        user = self.context['request'].user

        if not (user.role == 'admin' or instance.created_by == user):
             raise PermissionDenied("У вас нет прав на изменение статуса этого заказа.")

        if old_status == 'rejected' and new_status != 'rejected':
            raise serializers.ValidationError("Нельзя изменить статус отклоненного заказа")
        if old_status == 'confirmed' and new_status != 'confirmed':
            # Только админ может отменить подтвержденный (если это нужно?) - пока запрещаем всем
            # if user.role != 'admin':
             raise serializers.ValidationError("Нельзя изменить статус подтвержденного заказа")

        processed = False
        if instance.order_type == 'admin_to_partner':
            if user.role != 'admin':
                 raise PermissionDenied("Только администратор может изменять статус этого типа заказа.")

            if new_status == 'confirmed' and old_status == 'in_process':
                self._process_confirmed_admin_to_partner(instance)
                processed = True
            elif new_status == 'rejected' and old_status == 'in_process':
                self._process_rejected_admin_to_partner(instance)
                processed = True

        # --- ИЗМЕНЕНИЕ 3: Явная проверка для partner_to_store ---
        elif instance.order_type == 'partner_to_store':
            if new_status != 'confirmed':
                 # Предотвращаем любое изменение статуса для этого типа
                 raise serializers.ValidationError(f"Статус заказа магазину ('{instance.status}') не может быть изменен.")
            # Если статус уже 'confirmed' и пытаются установить 'confirmed', ничего не делаем
            processed = True # Считаем обработанным

        # Обновляем статус только если он изменился и был обработан или не требовал обработки
        if old_status != new_status:
             if processed:
                  instance.status = new_status
                  instance.save(update_fields=['status'])
                  logger.info(f"Статус заказа {instance.id} изменен на {new_status} пользователем {user.id}")
             else:
                  # Сюда не должны попасть при текущей логике, но на всякий случай
                  logger.warning(f"Попытка изменить статус заказа {instance.id} с '{old_status}' на '{new_status}' не была обработана.")
                  # Не меняем статус, если не было явной обработки

        return instance

    # Методы _process_confirmed_admin_to_partner и _process_rejected_admin_to_partner остаются как в предыдущем ответе

    def _process_confirmed_admin_to_partner(self, order):
        """Обработка подтверждения заказа от администратора к партнеру"""
        inventory_updates = {} # {product_id: quantity_to_add}
        for item in order.order_items.all():
            inventory_updates[item.product_id] = inventory_updates.get(item.product_id, 0) + item.quantity

        if inventory_updates:
            with transaction.atomic():
                 partner_inventory = PartnerInventory.objects.select_for_update().filter(
                     partner=order.partner, product_id__in=inventory_updates.keys()
                 )
                 inventory_map = {inv.product_id: inv for inv in partner_inventory}
                 new_inventory = []
                 updates = []

                 for product_id, quantity_to_add in inventory_updates.items():
                      inventory = inventory_map.get(product_id)
                      if inventory:
                           inventory.quantity += quantity_to_add
                           updates.append(inventory)
                      else:
                           new_inventory.append(
                                PartnerInventory(
                                     partner=order.partner,
                                     product_id=product_id,
                                     quantity=quantity_to_add
                                 )
                           )

                 if new_inventory:
                      PartnerInventory.objects.bulk_create(new_inventory)
                      logger.info(f"Создано {len(new_inventory)} новых записей инвентаря для партнера {order.partner.id} по заказу {order.id}")
                 if updates:
                      PartnerInventory.objects.bulk_update(updates, ['quantity'])
                      logger.info(f"Обновлено {len(updates)} записей инвентаря для партнера {order.partner.id} по заказу {order.id}")


    def _process_rejected_admin_to_partner(self, order):
        """Обработка отклонения заказа от администратора к партнеру"""
        products_to_restore = {} # {product_id: quantity_to_restore}
        for item in order.order_items.all():
            products_to_restore[item.product_id] = products_to_restore.get(item.product_id, 0) + item.quantity

        if products_to_restore:
            with transaction.atomic():
                 products = Product.objects.select_for_update().filter(id__in=products_to_restore.keys())
                 product_map = {p.id: p for p in products}
                 updates = []
                 for product_id, quantity_to_restore in products_to_restore.items():
                      product = product_map.get(product_id)
                      if product:
                           product.quantity += quantity_to_restore
                           updates.append(product)
                      else:
                           logger.warning(f"Товар {product_id} не найден при возврате на склад для заказа {order.id}")
                 if updates:
                      Product.objects.bulk_update(updates, ['quantity'])
                      logger.info(f"Возвращено {len(updates)} позиций товаров на склад администратора по отклоненному заказу {order.id}")



# --- DefectGroupSerializer ---
# (без изменений, как в предыдущем ответе)
# В serializers.py исправить DefectGroupSerializer

class DefectGroupSerializer(serializers.Serializer):
    """Сериализатор для добавления группы бракованных товаров"""
    defects = serializers.ListField(
        child=serializers.DictField(required=True),
        min_length=1
    )

    def validate_defects(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Поле 'defects' должно быть списком.")

        for item in value:
            if not isinstance(item, dict):
                raise serializers.ValidationError("Каждый элемент в 'defects' должен быть словарем.")

            # Исправлено: используем 'product' вместо 'product_id'
            if 'product' not in item or not isinstance(item['product'], int):
                raise serializers.ValidationError("Каждый элемент брака должен содержать 'product' (integer).")

            if 'quantity' not in item or not isinstance(item['quantity'], int) or item['quantity'] <= 0:
                raise serializers.ValidationError(
                    "Каждый элемент брака должен содержать 'quantity' (positive integer).")

            if 'description' in item and not isinstance(item['description'], str):
                raise serializers.ValidationError("Поле 'description' должно быть строкой.")

        return value

    @transaction.atomic
    def create(self, validated_data):
        order = self.context.get('order')
        if not order:
            raise serializers.ValidationError("Не удалось определить заказ для добавления брака.")

        # Удалена проверка типа заказа и статуса, так как мы создаём виртуальный заказ автоматически

        defects_data = validated_data.get('defects', [])
        created_defects = []

        for defect_data in defects_data:
            # Исправлено: используем 'product' вместо 'product_id'
            product_id = defect_data['product']
            quantity = defect_data['quantity']
            description = defect_data.get('description', '')

            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                logger.warning(f"Товар с ID {product_id} не найден при добавлении брака. Пропуск.")
                continue

            try:
                defect = DefectItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    description=description
                )
                created_defects.append(defect)
                logger.info(f"Добавлен брак: {quantity} шт. товара '{product.name}' к заказу {order.id}")
            except Exception as e:
                logger.error(f"Ошибка при создании DefectItem для товара {product_id} в заказе {order.id}: {e}")
                raise serializers.ValidationError("Ошибка при сохранении брака.")

        if not created_defects:
            raise serializers.ValidationError("Не удалось добавить ни один элемент брака. Проверьте данные.")

        return created_defects