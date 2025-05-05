# apps/orders/views.py
from rest_framework import viewsets, permissions, status, filters, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum, Count, Prefetch, F # Добавили Prefetch
from datetime import datetime, date, time # Добавили date, time
from django.utils import timezone # Добавили timezone
from django.shortcuts import get_object_or_404, Http404 # Добавили Http404
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound # Добавили

from .models import Order, OrderItem, DefectItem
from .serializers import (
    OrderSerializer,
    OrderWithItemsSerializer,
    OrderStatusUpdateSerializer,
    OrderItemSerializer,
    DefectItemSerializer,
    DefectGroupSerializer,
)
# Импортируем нужные модели и разрешения
from apps.stores.models import Store
from apps.users.permissions import IsAdminUser, IsPartnerUser, IsOwnerOrAdmin
from django.db import transaction
import logging
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.utils import timezone
from decimal import Decimal


logger = logging.getLogger(__name__)


class OrderViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с заказами.
    Поддерживает фильтрацию по дате создания.
    """
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # Добавляем фильтры по дате создания
    filterset_fields = {
        'order_type': ['exact'],
        'status': ['exact', 'in'],
        'is_group_order': ['exact'],
        'store': ['exact'],
        'partner': ['exact'],
        # ИЗМЕНЕНИЕ: Добавляем фильтры по дате (точное совпадение и диапазон)
        'created_at': ['exact', 'date', 'date__gte', 'date__lte', 'year', 'month', 'day'],
    }
    search_fields = ['store__name', 'partner__email', 'partner__first_name']
    ordering_fields = ['created_at', 'updated_at'] # Убрали total_price для производительности
    ordering = ['-created_at'] # Новые заказы сверху

    def get_queryset(self):
        user = self.request.user
        # Оптимизация запросов
        queryset = Order.objects.select_related(
            'created_by', 'partner', 'store', 'store__city'
        ).prefetch_related(
            # Prefetch для свойств total_price, total_bonus_items, total_items_quantity
            Prefetch('order_items', queryset=OrderItem.objects.select_related('product')),
            Prefetch('defect_items', queryset=DefectItem.objects.select_related('product'))
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
            return OrderWithItemsSerializer
        elif self.action in ['update', 'partial_update'] and 'status' in self.request.data:
            return OrderStatusUpdateSerializer
        return OrderSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAdminUser()]
        elif self.action in ['update', 'partial_update']:
            # Обновлять статус может админ или создатель (проверяется в OrderStatusUpdateSerializer)
            # Обновлять другие поля заказа - возможно, только админ? Уточнить.
            # Пока оставляем IsOwnerOrAdmin (проверяет created_by или partner)
            return [IsOwnerOrAdmin()]
        return [permissions.IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        logger.info(f"Попытка создания заказа пользователем {request.user.email}. Данные: {request.data}")
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            logger.info(f"Заказ ID {instance.id} успешно создан пользователем {request.user.email}.")
            headers = self.get_success_headers(serializer.data)
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

    @action(detail=True, methods=['post'], url_path='update-status') # Явный путь для action
    @swagger_auto_schema(
        operation_summary="Обновление статуса заказа",
        request_body=OrderStatusUpdateSerializer,
        responses={200: OrderSerializer, 400: "Ошибка валидации/Неверный переход", 403: "Нет прав"}
    )
    def update_status(self, request, pk=None):
        """Обновление статуса заказа (только Админ для admin_to_partner)."""
        order = self.get_object()
        serializer = OrderStatusUpdateSerializer(
            instance=order,
            data=request.data,
            context={'request': request}
        )
        try:
             serializer.is_valid(raise_exception=True)
             updated_order = serializer.save()
             logger.info(f"Статус заказа ID {order.id} обновлен на {updated_order.status} пользователем {request.user.email}")
             return Response(OrderSerializer(updated_order, context=self.get_serializer_context()).data)
        except (serializers.ValidationError, PermissionDenied) as e:
             logger.warning(f"Ошибка обновления статуса заказа {order.id} пользователем {request.user.email}: {e.detail if hasattr(e, 'detail') else str(e)}")
             error_detail = e.detail if hasattr(e, 'detail') else {"detail": str(e)}
             status_code = status.HTTP_403_FORBIDDEN if isinstance(e, PermissionDenied) else status.HTTP_400_BAD_REQUEST
             return Response(error_detail, status=status_code)
        except Exception as e:
             logger.exception(f"Необработанная ошибка при обновлении статуса заказа {order.id} пользователем {request.user.email}: {e}")
             return Response({"error": "Возникла ошибка при обновлении статуса."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # --- Actions для фильтрации списков (можно использовать стандартные фильтры) ---
    # Оставляем их для обратной совместимости или если нужна особая логика

    @action(detail=False, methods=['get'], url_path='admin-orders')
    @swagger_auto_schema(operation_summary="Заказы Админу (admin_to_partner)")
    def admin_orders(self, request):
        """Получение заказов от партнера к администратору"""
        queryset = self.filter_queryset(self.get_queryset().filter(order_type='admin_to_partner'))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='store-orders')
    @swagger_auto_schema(operation_summary="Заказы Магазинам (partner_to_store)")
    def store_orders(self, request):
        """Получение заказов от партнера к магазину"""
        queryset = self.filter_queryset(self.get_queryset().filter(order_type='partner_to_store'))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='in-process')
    @swagger_auto_schema(operation_summary="Заказы в обработке")
    def in_process(self, request):
        """Получение заказов в обработке (status='in_process')"""
        queryset = self.filter_queryset(self.get_queryset().filter(status='in_process'))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    # Action statistics можно оставить для общих цифр, если нужно
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Получение общей статистики по заказам для текущего пользователя/админа"""
        queryset = self.get_queryset() # Фильтрует по правам
        valid_orders_queryset = queryset.annotate(item_count=Count('order_items')).filter(item_count__gt=0) # Только с товарами

        total_orders = valid_orders_queryset.count()
        status_counts = valid_orders_queryset.values('status').annotate(count=Count('id')).order_by('status')
        type_counts = valid_orders_queryset.values('order_type').annotate(count=Count('id')).order_by('order_type')
        group_type_counts = valid_orders_queryset.values('is_group_order').annotate(count=Count('id'))
        confirmed_orders_price = valid_orders_queryset.filter(status='confirmed').aggregate(
             total=Sum(F('order_items__price') * F('order_items__quantity')) # Суммируем по связанным элементам
        )['total'] or Decimal('0.00')

        return Response({
            'total_orders': total_orders,
            'status_counts': {item['status']: item['count'] for item in status_counts},
            'type_counts': {item['order_type']: item['count'] for item in type_counts},
            'group_type_counts': {'group': next((item['count'] for item in group_type_counts if item['is_group_order']), 0),
                                   'single': next((item['count'] for item in group_type_counts if not item['is_group_order']), 0)},
            'confirmed_orders_price': float(confirmed_orders_price),
        })

    @action(detail=False, methods=['get'], url_path='get-store-orders')
    @swagger_auto_schema(operation_summary="Получить заказы магазина по дате")
    def get_store_orders(self, request):
        """Получение заказов магазина по дате"""
        store_id = request.query_params.get('store_id')
        date_str = request.query_params.get('date')

        if not store_id: return Response({"detail": "Необходимо указать ID магазина"}, status=status.HTTP_400_BAD_REQUEST)
        if not date_str: return Response({"detail": "Необходимо указать дату"}, status=status.HTTP_400_BAD_REQUEST)

        try: target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError: return Response({"detail": "Неверный формат даты"}, status=status.HTTP_400_BAD_REQUEST)

        # Используем get_queryset для проверки прав доступа
        orders = self.get_queryset().filter(
            store_id=store_id,
            created_at__date=target_date,
            order_type='partner_to_store'
        ).annotate(item_count=Count('order_items')).filter(item_count__gt=0) # Только с товарами

        order_data = [{
            'order_id': order.id,
            'created_at': order.created_at.isoformat(),
            'total_price': float(order.total_price), # Используем свойство
            'items_count': order.item_count # Используем аннотацию
        } for order in orders]

        return Response({
            'store_id': store_id, 'date': target_date.isoformat(),
            'orders_count': len(order_data), 'orders': order_data
        })


# --- OrderItemViewSet ---
class OrderItemViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с элементами заказа.
    Доступ через /api/orders/{order_pk}/items/
    """
    serializer_class = OrderItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = OrderItem.objects.none() # Базовый queryset пустой, определяется в get_queryset

    def get_order(self):
        """Получает объект заказа из URL и проверяет права."""
        if getattr(self, '_order', None) is None: # Кэшируем результат
             if getattr(self, 'swagger_fake_view', False): self._order = None; return self._order
             order_pk = self.kwargs.get('order_pk')
             if not order_pk: logger.error("OrderItemViewSet вызван без order_pk"); self._order = None; return self._order
             try:
                 order = get_object_or_404(Order, pk=order_pk)
                 user = self.request.user
                 if not (user.role == 'admin' or order.created_by == user or order.partner == user):
                      raise PermissionDenied("У вас нет доступа к этому заказу.")
                 self._order = order
             except Http404: # Заменяем на NotFound
                  raise NotFound(detail="Заказ не найден.")
             except PermissionDenied: # Пробрасываем дальше
                  raise
        return self._order

    def get_queryset(self):
        order = self.get_order()
        if order: return OrderItem.objects.filter(order=order).select_related('product')
        return OrderItem.objects.none()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        order = self.get_order()
        if order: context['order'] = order
        context['request'] = self.request
        return context

    def get_permissions(self):
        order = self.get_order()
        if order is None and not getattr(self, 'swagger_fake_view', False):
             return [permissions.DenyAll()]

        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
             if order and order.status != 'in_process': return [permissions.DenyAll()]
             return [IsOwnerOrAdmin()] # Проверяет создателя заказа или админа
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        order = self.get_order()
        if not order: raise ValidationError("Не удалось определить заказ.")
        if order.status != 'in_process': raise ValidationError("Нельзя добавить товар в обработанный заказ.")
        # Сериализатор должен проверить остатки перед save()
        serializer.save(order=order)
        # TODO: Подумать о пересчете total_price заказа после добавления/изменения элемента?
        # order.total_price = order.calculate_total_price() # Пример
        # order.save()

    def perform_update(self, serializer):
         # TODO: Логика пересчета, если нужно
         serializer.save()

    def perform_destroy(self, instance):
         # TODO: Логика пересчета, если нужно
         logger.warning(f"Пользователь {self.request.user.email} удаляет элемент заказа ID {instance.id} из заказа ID {instance.order.id}")
         instance.delete()


# --- DefectItemViewSet ---

    # apps/orders/views.py

    # Убедись, что все эти импорты присутствуют в начале файла
    from rest_framework import viewsets, permissions, status, filters, serializers
    from rest_framework.decorators import action
    from rest_framework.response import Response
    from django_filters.rest_framework import DjangoFilterBackend
    from django.db.models import Q, Sum, Count, Prefetch
    from datetime import datetime, date, time
    from django.utils import timezone
    from django.shortcuts import get_object_or_404, Http404
    from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
    from drf_yasg.utils import swagger_auto_schema
    from drf_yasg import openapi
    from django.db import transaction
    import logging

    from .models import Order, OrderItem, DefectItem
    from .serializers import (
        OrderSerializer, OrderWithItemsSerializer, OrderStatusUpdateSerializer,
        OrderItemSerializer, DefectItemSerializer, DefectGroupSerializer
    )
    from apps.stores.models import Store  # Импортируем Store
    from apps.users.permissions import IsAdminUser, IsPartnerUser, IsOwnerOrAdmin

    logger = logging.getLogger(__name__)

    # --- OrderViewSet ---
    # (Код OrderViewSet и OrderItemViewSet без изменений по сравнению с версиями,
    # где исправляли бонусы и SET_NULL)

    # --- ИСПРАВЛЕННЫЙ DefectItemViewSet ---
class DefectItemViewSet(viewsets.ModelViewSet):
    serializer_class = DefectItemSerializer
    permission_classes = [permissions.IsAuthenticated]  # Права уточняются ниже
    queryset = DefectItem.objects.none()  # Определяется в get_queryset
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {  # Уточняем фильтры
            'order': ['exact'],
            'order__store': ['exact'],  # Фильтр по магазину через заказ
            'product': ['exact'],
            'created_at': ['date', 'date__gte', 'date__lte'],  # Фильтр по дате создания брака
        }
    search_fields = ['product__name', 'description', 'order__store__name']  # Добавим поиск по магазину
    ordering_fields = ['created_at', 'quantity']
    ordering = ['-created_at']

    def get_order(self):
        if getattr(self, '_order', 'NOT_FETCHED') == 'NOT_FETCHED':
            if getattr(self, 'swagger_fake_view', False): self._order = None; return self._order
            order_pk = self.kwargs.get('order_pk')
            if not order_pk: self._order = None; return self._order  # Не вложенный URL
            try:
                    # Получаем заказ без проверки прав здесь, права проверим в get_permissions/actions
                order = get_object_or_404(Order.objects.select_related('store', 'partner', 'created_by'),
                                              pk=order_pk)
                self._order = order
            except Http404:
                raise NotFound(detail="Заказ не найден.")
        return self._order

    def get_queryset(self):
        user = self.request.user
        queryset = DefectItem.objects.select_related('order', 'product', 'order__store', 'order__partner')
        order = self.get_order()  # Пытаемся получить заказ из URL

        if order:  # Если URL вложенный /orders/{pk}/defects/
                # Проверяем доступ к этому конкретному заказу
            if not (user.role == 'admin' or order.created_by == user or order.partner == user):
                return DefectItem.objects.none()  # Нет доступа
            return queryset.filter(order=order)
            # Если URL /defects/ (общий список)
        elif not getattr(self, 'swagger_fake_view', False):
            if user.role == 'admin':
                return queryset  # Админ видит все
            elif user.role == 'partner':
                return queryset.filter(order__created_by=user)  # Партнер видит брак по своим заказам
            else:
                return DefectItem.objects.none()
        else:  # При генерации схемы для /defects/
            return DefectItem.objects.none()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        order = self.get_order()
        if order: context['order'] = order
        context['request'] = self.request
        return context

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]

        order = self.get_order()

        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsOwnerOrAdmin()]

        if self.action == 'create':
            # Все аутентифицированные могут создавать брак
            return [permissions.IsAuthenticated()]

        if self.action == 'add_group_by_store':
            # Все аутентифицированные могут добавлять брак
            return [permissions.IsAuthenticated()]

        return [permissions.IsAuthenticated()]

    # По умолчанию

    def perform_create(self, serializer):
        order = self.context.get('order')
        if not order:
            raise ValidationError("Создание брака возможно только через URL заказа: /api/orders/{order_pk}/defects/")

        # Удалена проверка роли - все могут добавлять брак
        serializer.save(order=order)

        # --- ИСПРАВЛЕННЫЙ action add_group_by_store ---

    @action(detail=False, methods=['post'], url_path='add-group-by-store')
    @swagger_auto_schema(
        operation_summary="Добавить брак по магазину и дате",
        operation_description="Находит последний подтвержденный заказ 'Партнер -> Магазин' для указанного магазина за указанную дату (по умолчанию сегодня) и добавляет к нему брак.",
        request_body=DefectGroupSerializer,
        manual_parameters=[
            openapi.Parameter('store_id', openapi.IN_QUERY, description="ID Магазина (обязательный)",
                              type=openapi.TYPE_INTEGER, required=True),
            openapi.Parameter('date', openapi.IN_QUERY, description="Дата заказа (YYYY-MM-DD, по умолч. сегодня)",
                              type=openapi.TYPE_STRING, format='date'),
        ],
        responses={201: DefectItemSerializer(many=True), 400: "Ошибка валидации/Не найден заказ",
                   403: "Нет доступа", 404: "Магазин не найден"}
    )
    def add_group_by_store(self, request):
        user = request.user
        store_id = request.query_params.get('store_id')
        date_str = request.query_params.get('date')

        if not store_id:
            return Response({"detail": "Параметр store_id обязателен"}, status=status.HTTP_400_BAD_REQUEST)

        # Получаем магазин
        try:
            store = get_object_or_404(Store, pk=int(store_id), is_deleted=False, is_active=True)
        except (ValueError, TypeError):
            return Response({"detail": "Неверный ID магазина"}, status=status.HTTP_400_BAD_REQUEST)
        except Http404:
            return Response({"detail": "Магазин не найден, неактивен или удален"}, status=status.HTTP_404_NOT_FOUND)

        # Определяем дату
        target_date = None
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({"detail": "Неверный формат даты"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Исправлено: используем локальную дату
            target_date = timezone.now().date()

        # Находим последний подходящий заказ
        order_filter = Q(store=store) & Q(order_type='partner_to_store') & Q(status='confirmed') & Q(
            created_at__date=target_date)

        order = Order.objects.filter(order_filter).order_by('-created_at').first()

        if not order:
            return Response({
                "detail": f"Подтвержденные заказы типа 'Партнер -> Магазин' для магазина '{store.name}' за {target_date.strftime('%d.%m.%Y')} не найдены."
            }, status=status.HTTP_404_NOT_FOUND)

        # Создаем и валидируем DefectGroupSerializer
        context = {'request': request, 'order': order}
        serializer = DefectGroupSerializer(data=request.data, context=context)

        try:
            serializer.is_valid(raise_exception=True)
            defects = serializer.save()
            logger.info(
                f"Пользователь {request.user.email} добавил группу брака ({len(defects)} шт.) к заказу {order.id} магазина {store.id} за {target_date}")

            # Используем DefectItemSerializer для ответа
            return Response(
                DefectItemSerializer(defects, many=True, context=context).data,
                status=status.HTTP_201_CREATED
            )
        except (serializers.ValidationError, PermissionDenied) as e:
            logger.warning(
                f"Ошибка добавления группы брака к заказу {order.id} магазина {store.id}: {e.detail if hasattr(e, 'detail') else str(e)}")
            error_detail = e.detail if hasattr(e, 'detail') else {"detail": str(e)}
            status_code = status.HTTP_403_FORBIDDEN if isinstance(e, PermissionDenied) else status.HTTP_400_BAD_REQUEST
            return Response(error_detail, status=status_code)
        except Exception as e:
            logger.exception(
                f"Необработанная ошибка при добавлении группы брака к заказу {order.id} магазина {store.id}: {e}")
            return Response({"error": "Ошибка при добавлении бракованных товаров."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    # --- Actions для получения списков брака ---
    @action(detail=False, methods=['get'], url_path='order-defects')
    @swagger_auto_schema(operation_summary="Получить брак по ID заказа")
    def order_defects(self, request):
        """Получение бракованных товаров по конкретному заказу"""
        order_id = request.query_params.get('order_id')
        if not order_id: return Response({"detail": "Необходимо указать ID заказа"}, status=status.HTTP_400_BAD_REQUEST)
        # get_queryset проверит права на заказ, если мы в контексте /orders/{pk}/defects/, но здесь нет order_pk
        # Поэтому получаем queryset и фильтруем вручную, ПРОВЕРЯЯ ПРАВА
        user = request.user
        try:
             order = get_object_or_404(Order, pk=int(order_id))
             if not (user.role == 'admin' or order.created_by == user or order.partner == user):
                  raise PermissionDenied("Нет доступа к этому заказу")
        except (ValueError, TypeError): return Response({"detail": "Неверный ID заказа"}, status=status.HTTP_400_BAD_REQUEST)
        except Http404: return Response({"detail": "Заказ не найден"}, status=status.HTTP_404_NOT_FOUND)
        except PermissionDenied as e: return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

        queryset = DefectItem.objects.filter(order=order).select_related('product')
        serializer = DefectItemSerializer(queryset, many=True, context={'request': request})
        total_defect_price = sum(defect.total_price for defect in queryset) or Decimal('0.00')
        return Response({"order_id": order.id, "defects": serializer.data, "total_quantity": queryset.aggregate(total=Sum('quantity'))['total'] or 0, "total_price": float(total_defect_price)})

    @action(detail=False, methods=['get'], url_path='store-defects')
    @swagger_auto_schema(operation_summary="Получить брак по магазину и дате")
    def store_defects(self, request):
        """Получение бракованных товаров по магазину и дате"""
        store_id = request.query_params.get('store_id')
        date_str = request.query_params.get('date')
        if not store_id: return Response({"detail": "Необходимо указать ID магазина"}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        try:
             store = get_object_or_404(Store, pk=int(store_id))
             if not (user.role == 'admin' or store.partner == user):
                  raise PermissionDenied("Нет доступа к этому магазину")
        except (ValueError, TypeError): return Response({"detail": "Неверный ID магазина"}, status=status.HTTP_400_BAD_REQUEST)
        except Http404: return Response({"detail": "Магазин не найден"}, status=status.HTTP_404_NOT_FOUND)
        except PermissionDenied as e: return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

        # Получаем базовый queryset (все дефекты) и фильтруем
        queryset = DefectItem.objects.filter(order__store=store).select_related('product', 'order')
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                queryset = queryset.filter(order__created_at__date=target_date)
            except ValueError: return Response({"detail": "Неверный формат даты"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = DefectItemSerializer(queryset, many=True, context={'request': request})
        total_defect_price = sum(defect.total_price for defect in queryset) or Decimal('0.00')
        # Группировка по товарам (как была)
        product_summary = {}
        # ... (код группировки) ...
        for defect in queryset:
             product = defect.product
             if product:
                  product_id = product.id
                  summary = product_summary.setdefault(product_id, {"product_id": product_id, "product_name": product.name,"total_quantity": 0,"total_price": 0.0})
                  summary["total_quantity"] += defect.quantity
                  summary["total_price"] += float(defect.total_price or 0)

        return Response({"store_id": store.id, "store_name": store.name, "filter_date": date_str, "defects": serializer.data, "total_quantity": queryset.aggregate(total=Sum('quantity'))['total'] or 0, "total_price": float(total_defect_price), "products_summary": list(product_summary.values())})