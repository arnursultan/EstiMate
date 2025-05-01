from rest_framework import viewsets, permissions, status, filters, serializers
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum, Count # Добавили Count
from datetime import datetime
from .models import Order, OrderItem, DefectItem
from .serializers import (
    OrderSerializer,
    OrderWithItemsSerializer,
    OrderStatusUpdateSerializer,
    OrderItemSerializer,
    DefectItemSerializer,
    DefectGroupSerializer,
    # StoreDebtPaymentSerializer, - УДАЛЕН ИЗ ИМПОРТОВ
    # StoreExpenseSerializer, - УДАЛЕН ИЗ ИМПОРТОВ
    # PartnerInventoryDetailSerializer - УДАЛЕН ИЗ ИМПОРТОВ
)
# Убрали импорты: Store, StoreDebt, StoreDebtPayment, StoreExpense, PartnerInventory
from apps.users.permissions import IsAdminUser, IsPartnerUser, IsOwnerOrAdmin # Импорт из users
# Убрали импорт PartnerInventorySerializer
from django.db import transaction
import logging
from django.shortcuts import get_object_or_404 # Добавили
from rest_framework.exceptions import PermissionDenied # Добавили

logger = logging.getLogger(__name__)


class OrderViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с заказами
    """
    serializer_class = OrderSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['order_type', 'status', 'is_group_order', 'store', 'partner']
    search_fields = ['store__name', 'partner__email', 'partner__first_name']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at'] # Новые заказы сверху

    def get_queryset(self):
        user = self.request.user
        # Оптимизация запросов
        queryset = Order.objects.select_related(
            'created_by', 'partner', 'store', 'store__city'
        ).prefetch_related(
            'order_items', 'order_items__product', 'defect_items', 'defect_items__product'
        )

        if user.role == 'admin':
            # Админ видит все заказы
            return queryset
        elif user.role == 'partner':
            # Партнеры видят только заказы, где они создатель ИЛИ получатель
            return queryset.filter(Q(created_by=user) | Q(partner=user))
        else:
            return Order.objects.none()

    def get_serializer_class(self):
        if self.action == 'create':
            # Используем OrderWithItemsSerializer, т.к. заказ без товаров бессмысленен
            return OrderWithItemsSerializer
        elif self.action in ['update', 'partial_update'] and 'status' in self.request.data:
             # Для обновления статуса используем отдельный сериализатор
            return OrderStatusUpdateSerializer
        # Во всех остальных случаях (list, retrieve) используем базовый
        return OrderSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        # Передаем items в контекст для OrderWithItemsSerializer, если они есть
        # Сериализатор сам проверит 'items' в request.data
        # context['items'] = self.request.data.get('items', [])
        # context['order_items'] = self.request.data.get('order_items', [])
        return context

    def get_permissions(self):
        if self.action == 'destroy':
            # Жесткое удаление только админу (не рекомендуется)
            return [IsAdminUser()]
        elif self.action in ['update', 'partial_update']:
            # Обновлять (менять статус) может админ или создатель? Зависит от логики.
            # OrderStatusUpdateSerializer содержит свою логику прав.
            # Общее обновление полей заказа - только админ?
            # Пока оставим IsOwnerOrAdmin (проверяет created_by или partner)
             return [IsOwnerOrAdmin()]
        # Создавать могут партнеры и админы (проверяется в create)
        # Читать могут владельцы и админы (проверяется в get_queryset)
        return [permissions.IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        logger.info(f"Попытка создания заказа пользователем {request.user.email}. Данные: {request.data}")
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            # Логика создания заказа, обновления остатков и создания долга - внутри serializer.create()
            instance = serializer.save()
            logger.info(f"Заказ ID {instance.id} успешно создан пользователем {request.user.email}.")
            headers = self.get_success_headers(serializer.data)
            # Возвращаем данные через OrderSerializer для консистентности ответа
            return Response(
                 OrderSerializer(instance, context=self.get_serializer_context()).data,
                 status=status.HTTP_201_CREATED,
                 headers=headers
             )
        except (serializers.ValidationError, PermissionDenied) as e:
            logger.warning(f"Ошибка валидации/прав при создании заказа пользователем {request.user.email}: {e.detail if hasattr(e, 'detail') else str(e)}")
            error_detail = e.detail if hasattr(e, 'detail') else {"detail": str(e)}
            status_code = status.HTTP_403_FORBIDDEN if isinstance(e, PermissionDenied) else status.HTTP_400_BAD_REQUEST
            return Response(error_detail, status=status_code)
        except Exception as e:
            logger.exception(f"Необработанная ошибка при создании заказа пользователем {request.user.email}: {str(e)}")
            return Response({"error": "Возникла ошибка при создании заказа."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated]) # Права проверяются внутри сериализатора
    def update_status(self, request, pk=None):
        """Обновление статуса заказа"""
        order = self.get_object() # Получаем заказ (права на чтение проверены)
        serializer = OrderStatusUpdateSerializer(
            instance=order,
            data=request.data,
            context={'request': request} # Передаем request для проверки прав в сериализаторе
        )
        try:
             serializer.is_valid(raise_exception=True)
             serializer.save()
             logger.info(f"Статус заказа ID {order.id} обновлен на {order.status} пользователем {request.user.email}")
             # Возвращаем полные данные заказа
             return Response(OrderSerializer(order, context=self.get_serializer_context()).data)
        except (serializers.ValidationError, PermissionDenied) as e:
             logger.warning(f"Ошибка обновления статуса заказа {order.id} пользователем {request.user.email}: {e.detail if hasattr(e, 'detail') else str(e)}")
             error_detail = e.detail if hasattr(e, 'detail') else {"detail": str(e)}
             status_code = status.HTTP_403_FORBIDDEN if isinstance(e, PermissionDenied) else status.HTTP_400_BAD_REQUEST
             return Response(error_detail, status=status_code)
        except Exception as e:
             logger.exception(f"Необработанная ошибка при обновлении статуса заказа {order.id} пользователем {request.user.email}: {e}")
             return Response({"error": "Возникла ошибка при обновлении статуса."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Остальные actions (admin_orders, store_orders, in_process, statistics, get_store_orders) остаются без изменений

# --- OrderItemViewSet ---
class OrderItemViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с элементами заказа.
    Доступ через /api/orders/{order_pk}/items/
    """
    serializer_class = OrderItemSerializer
    permission_classes = [permissions.IsAuthenticated] # Права на конкретные действия проверяются ниже
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product']
    search_fields = ['product__name']
    ordering_fields = ['created_at', 'quantity', 'price']
    ordering = ['-created_at']

    def get_order(self):
        """Получает объект заказа из URL"""
        order_pk = self.kwargs.get('order_pk')
        order = get_object_or_404(Order, pk=order_pk)
        # Проверяем доступ к самому заказу
        user = self.request.user
        if not (user.role == 'admin' or order.created_by == user or order.partner == user):
             raise PermissionDenied("У вас нет доступа к этому заказу.")
        return order

    def get_queryset(self):
        order = self.get_order()
        return OrderItem.objects.filter(order=order).select_related('product')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['order'] = self.get_order() # Передаем заказ в контекст
        context['request'] = self.request
        return context

    def get_permissions(self):
        order = self.get_order()
        # Разрешаем чтение всем, кто имеет доступ к заказу
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        # Изменять/удалять элементы может только админ или создатель заказа,
        # и только если заказ 'in_process'
        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
             if order.status != 'in_process':
                  # Нельзя менять подтвержденные или отклоненные заказы
                  return [permissions.DenyAll()] # Используем DenyAll
             # Проверяем создателя или админа
             return [IsOwnerOrAdmin()] # IsOwnerOrAdmin проверит created_by или admin role
        return [permissions.IsAuthenticated()] # По умолчанию

    def perform_create(self, serializer):
        # Заказ уже установлен в контексте и будет использован сериализатором
        # Проверка наличия и остатков делается в сериализаторе
        # TODO: Подумать об обновлении остатков при добавлении/изменении элемента в 'in_process' заказе
        # Сейчас остатки меняются только при подтверждении/отклонении всего заказа
        serializer.save()

    def perform_update(self, serializer):
         # TODO: Подумать об обновлении остатков при изменении количества
         serializer.save()

    def perform_destroy(self, instance):
         # TODO: Подумать об обновлении остатков при удалении элемента
         logger.warning(f"Пользователь {self.request.user.email} удаляет элемент заказа ID {instance.id} из заказа ID {instance.order.id}")
         instance.delete()


# --- DefectItemViewSet ---
class DefectItemViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с бракованными товарами в заказе.
    Доступ через /api/orders/{order_pk}/defects/ или /api/defects/
    """
    serializer_class = DefectItemSerializer
    permission_classes = [permissions.IsAuthenticated] # Права проверяются ниже
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['order', 'product']
    search_fields = ['product__name', 'description']
    ordering_fields = ['created_at', 'quantity']
    ordering = ['-created_at']

    def get_order(self):
        """Получает объект заказа из URL (если используется вложенный роутер)"""
        order_pk = self.kwargs.get('order_pk')
        if order_pk:
             order = get_object_or_404(Order, pk=order_pk)
             # Проверяем доступ к заказу
             user = self.request.user
             if not (user.role == 'admin' or order.created_by == user or order.partner == user):
                  raise PermissionDenied("У вас нет доступа к этому заказу.")
             return order
        return None

    def get_queryset(self):
        user = self.request.user
        queryset = DefectItem.objects.select_related('order', 'product', 'order__store', 'order__partner')

        # Если доступ через вложенный URL /orders/{order_pk}/defects/
        order = self.get_order()
        if order:
             return queryset.filter(order=order)

        # Если доступ через /defects/ (общий список)
        if user.role == 'admin':
            return queryset # Админ видит все
        elif user.role == 'partner':
            # Партнер видит брак только по заказам, которые он СОЗДАЛ
            return queryset.filter(order__created_by=user)
        else:
            return DefectItem.objects.none()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        order = self.get_order()
        if order:
            context['order'] = order # Передаем заказ, если есть
        context['request'] = self.request
        return context

    def get_permissions(self):
         # Читать могут все, кто видит заказ (проверяется в get_queryset)
         if self.action in ['list', 'retrieve']:
              return [permissions.IsAuthenticated()]
         # Создавать/менять/удалять может админ или создатель заказа
         # и только если заказ partner_to_store и confirmed
         elif self.action in ['create', 'update', 'partial_update', 'destroy', 'add_group']:
              order = self.get_order()
              # Если order есть (вложенный роутер), проверяем его
              if order:
                   if order.order_type != 'partner_to_store' or order.status != 'confirmed':
                        return [permissions.DenyAll()]
                   # Используем IsOwnerOrAdmin (проверит created_by или админа)
                   return [IsOwnerOrAdmin()]
              else:
                   # Если доступ через /defects/ (не вложенный), разрешаем только админу менять/удалять
                   # Создание брака напрямую через /defects/ запрещено
                   if self.action == 'create':
                        return [permissions.DenyAll()]
                   return [IsAdminUser()]
         return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
         # Заказ должен быть в контексте
         order = self.context.get('order')
         if not order:
              raise serializers.ValidationError("Не удалось определить заказ для добавления брака.")
         # Проверки и права уже должны быть выполнены в get_permissions и validate сериализатора
         serializer.save(order=order) # Передаем заказ явно

    # Action add_group остается как был, но теперь использует контекст

    @action(detail=False, methods=['post'])
    def add_group(self, request, order_pk=None): # Принимаем order_pk из URL
        """Добавление группы бракованных товаров для заказа"""
        # Получаем заказ (и проверяем права)
        try:
             order = self.get_order()
             if not order: # Если вдруг доступ не через вложенный URL
                  return Response({"error": "Используйте URL /api/orders/{order_pk}/defects/add_group/"}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
             return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

        # Передаем заказ в контекст сериализатора
        context = self.get_serializer_context()
        context['order'] = order

        serializer = DefectGroupSerializer(data=request.data, context=context)
        try:
            serializer.is_valid(raise_exception=True)
            # Права доступа проверяются внутри сериализатора
            defects = serializer.save() # save вызовет create сериализатора
            logger.info(f"Пользователь {request.user.email} добавил группу брака ({len(defects)} шт.) к заказу {order.id}")
            return Response(
                DefectItemSerializer(defects, many=True, context=context).data,
                status=status.HTTP_201_CREATED
            )
        except (serializers.ValidationError, PermissionDenied) as e:
            logger.warning(f"Ошибка добавления группы брака к заказу {order.id} пользователем {request.user.email}: {e.detail if hasattr(e, 'detail') else str(e)}")
            error_detail = e.detail if hasattr(e, 'detail') else {"detail": str(e)}
            status_code = status.HTTP_403_FORBIDDEN if isinstance(e, PermissionDenied) else status.HTTP_400_BAD_REQUEST
            return Response(error_detail, status=status_code)
        except Exception as e:
            logger.exception(f"Необработанная ошибка при добавлении группы брака к заказу {order.id}: {e}")
            return Response({"error": "Ошибка при добавлении бракованных товаров."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def order_defects(self, request):
        """Получение бракованных товаров по конкретному заказу"""
        order_id = request.query_params.get('order_id')
        if not order_id:
            return Response(
                {"detail": "Необходимо указать ID заказа"},
                status=status.HTTP_400_BAD_REQUEST
            )

        queryset = self.get_queryset().filter(order_id=order_id)

        # Проверяем, что заказ существует и имеет элементы
        from .models import Order
        try:
            order = Order.objects.get(id=order_id)
            if order.order_items.count() == 0:
                return Response({
                    "warning": "Заказ не содержит товаров",
                    "defects": [],
                    "total_quantity": 0,
                    "total_price": 0
                })
        except Order.DoesNotExist:
            return Response(
                {"detail": "Заказ не найден"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = DefectItemSerializer(queryset, many=True)

        # Рассчитываем общую стоимость бракованных товаров
        total_defect_price = sum(defect.total_price for defect in queryset)

        return Response({
            "defects": serializer.data,
            "total_quantity": queryset.aggregate(total=Sum('quantity'))['total'] or 0,
            "total_price": total_defect_price
        })

    @action(detail=False, methods=['get'])
    def store_defects(self, request):
        store_id = request.query_params.get('store_id')
        date_str = request.query_params.get('date')

        if not store_id:
            return Response(
                {"detail": "Необходимо указать ID магазина"},
                status=status.HTTP_400_BAD_REQUEST
            )

        queryset = self.get_queryset().filter(order__store_id=store_id)

        # Проверка статистики по магазину
        from apps.stores.models import Store
        try:
            store = Store.objects.get(id=store_id)
        except Store.DoesNotExist:
            return Response(
                {"detail": "Магазин не найден"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Фильтрация по дате, если указана
        if date_str:
            try:
                from datetime import datetime
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                queryset = queryset.filter(order__created_at__date=date)
            except ValueError:
                return Response(
                    {"detail": "Неверный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = DefectItemSerializer(queryset, many=True)

        # Рассчитываем общую стоимость бракованных товаров
        total_defect_price = sum(defect.total_price for defect in queryset)

        # Группируем по товарам
        product_summary = {}
        for defect in queryset:
            product_id = defect.product_id
            if product_id not in product_summary:
                product_summary[product_id] = {
                    "product_id": product_id,
                    "product_name": defect.product.name,
                    "total_quantity": 0,
                    "total_price": 0
                }

            product_summary[product_id]["total_quantity"] += defect.quantity
            product_summary[product_id]["total_price"] += float(defect.total_price)

        return Response({
            "defects": serializer.data,
            "total_quantity": queryset.aggregate(total=Sum('quantity'))['total'] or 0,
            "total_price": float(total_defect_price),
            "products_summary": list(product_summary.values())
        })


