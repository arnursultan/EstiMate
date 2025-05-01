from django.db import transaction
from rest_framework import viewsets, permissions, status, filters, serializers
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Sum, Q, Count # Добавим Count
from .models import City, Store, StoreDebt, StoreDebtPayment # Убрали StoreExpense
from .serializers import (
    CitySerializer,
    StoreSerializer,
    StoreDebtSerializer,
    StoreListSerializer,
    StoreDebtPaymentSerializer, # Добавили
    # StoreExpenseSerializer - УДАЛЕН
)
from datetime import datetime, timedelta
# Импортируем разрешения из users
from apps.users.permissions import IsAdminUser, IsPartnerUser, IsOwnerOrAdmin
# Убрали импорты StoreExpenseSerializer, StoreExpense
from rest_framework.views import APIView
from django.core.cache import cache
import logging
from django.shortcuts import get_object_or_404 # Добавим
from rest_framework.exceptions import PermissionDenied # Добавим
from decimal import Decimal
from django.db.models import F
from apps.finance.services import PartnerStatisticsService
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from apps.finance.services import StoreGroupStatisticsService # Импорт нового сервиса
from apps.finance.views import get_date_range_from_params




logger = logging.getLogger(__name__)

class CityViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с городами
    """
    queryset = City.objects.all()
    serializer_class = CitySerializer
    # Права доступа определяются в get_permissions
    # permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]


# apps/stores/views.py
from django.db import transaction, models # Добавим models и F
from django.db.models import Sum, Q, Count, F # Добавим F
from rest_framework import viewsets, permissions, status, filters, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from datetime import datetime, timedelta, date, time # Добавим date, time
from decimal import Decimal # Добавим Decimal
import logging

# Импорты моделей
from .models import City, Store, StoreDebt, StoreDebtPayment
from apps.orders.models import Order, OrderItem, DefectItem # Для financial_summary
from apps.finance.models import PartnerExpense # Для financial_summary
from apps.users.models import User # Для проверки партнера

# Импорты сериализаторов
from .serializers import (
    CitySerializer,
    StoreSerializer,
    StoreDebtSerializer,
    StoreListSerializer,
    StoreDebtPaymentSerializer
)

# Импорты разрешений
from apps.users.permissions import IsAdminUser, IsPartnerUser, IsOwnerOrAdmin

# Импорты для financial_summary и др.
from rest_framework.views import APIView
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.finance.views import get_date_range_from_params # Импортируем хелпер

logger = logging.getLogger(__name__)

class CityViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с городами
    """
    queryset = City.objects.all()
    serializer_class = CitySerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]


# --- ИСПРАВЛЕННЫЙ StoreViewSet ---
class StoreViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с магазинами.
    Партнеры видят все активные, неудаленные магазины.
    Админы видят все и могут фильтровать по статусу/удалению.
    """
    serializer_class = StoreSerializer
    permission_classes = [permissions.IsAuthenticated] # Базовое, уточняется в методах
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['city', 'status', 'is_active', 'partner']
    search_fields = ['name', 'inn', 'address', 'phone', 'partner__first_name', 'partner__last_name', 'partner__email']
    ordering_fields = ['name', 'created_at', 'city__name', 'partner__last_name']
    ordering = ['name']

    def get_queryset(self):
        """Фильтрует магазины в зависимости от роли пользователя и query-параметров."""
        user = self.request.user
        # Начинаем со всех магазинов, включая удаленные, чтобы админ мог их видеть
        queryset = Store.objects.select_related('city', 'partner')

        # --- Фильтрация для АДМИНА ---
        if user.role == 'admin':
            is_deleted_param = self.request.query_params.get('is_deleted')
            is_active_param = self.request.query_params.get('is_active')

            show_deleted = is_deleted_param is not None and is_deleted_param.lower() == 'true'

            if show_deleted:
                # Показываем ТОЛЬКО удаленные
                queryset = queryset.filter(is_deleted=True)
                # Фильтр is_active для удаленных обычно не применяется
            else:
                # По умолчанию или is_deleted=false - показываем НЕ удаленные
                queryset = queryset.filter(is_deleted=False)
                # И применяем фильтр is_active (по умолчанию показываем активные)
                show_active = True
                if is_active_param is not None:
                    show_active = is_active_param.lower() == 'true'
                queryset = queryset.filter(is_active=show_active)

        # --- Фильтрация для ПАРТНЕРА ---
        elif user.role == 'partner':
            # Партнер видит ВСЕ активные и НЕ удаленные магазины
            queryset = queryset.filter(is_active=True, is_deleted=False)
        # --- КОНЕЦ ИЗМЕНЕНИЯ для Партнера ---

        else:
            # Другие роли ничего не видят
            queryset = Store.objects.none()

        # Возвращаем отсортированный queryset
        # Стандартный OrderingFilter применит сортировку из query params, если она есть
        # ordering в атрибутах класса задает сортировку по умолчанию
        return queryset # ordering применится автоматически

    def get_serializer_class(self):
        if self.action == 'list':
            return StoreListSerializer
        return StoreSerializer

    def get_permissions(self):
        # Права на list/retrieve проверяются в get_queryset
        if self.action == 'create':
            # Партнеры и админы могут создавать
            return [permissions.IsAuthenticated()] # Роль проверяется в perform_create
        elif self.action in ['update', 'partial_update']:
            # Только владелец или админ
            return [IsOwnerOrAdmin()] # Проверяет obj.partner == user
        elif self.action == 'destroy':
             # Жесткое удаление - не рекомендуется, используем soft_delete
            return [IsAdminUser()]
        # Права для actions определяются в декораторе @action
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        # Переопределяем для установки партнера и статуса по умолчанию
        user = self.request.user
        if user.role == 'partner':
             # Партнер создает магазин для себя
             serializer.save(partner=user, status='approved', is_deleted=False)
        elif user.role == 'admin':
             # Админ должен передать 'partner' в данных (проверяется в сериализаторе)
             # Статус и is_deleted тоже устанавливаем по умолчанию
             serializer.save(status='approved', is_deleted=False)
        else:
            # На всякий случай
            raise PermissionDenied("У вас нет прав для создания магазина")

    # --- Actions ---

    @action(detail=False, methods=['get'])
    def with_debt(self, request):
        """Получение списка магазинов с долгами"""
        # Оптимизированный запрос (без изменений)
        queryset = self.get_queryset().annotate(
            debt_sum=Sum('debts__amount', filter=Q(debts__is_paid=False)),
            paid_sum=Sum('debt_payments__amount')
        ).filter(
            Q(debt_sum__isnull=False) & Q(paid_sum__isnull=True) & Q(debt_sum__gt=0) |
            Q(debt_sum__isnull=False) & Q(paid_sum__isnull=False) & Q(debt_sum__gt=F('paid_sum'))
        )
        serializer = StoreListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    @swagger_auto_schema( # Добавляем документацию
        operation_summary="Финансовая сводка по магазину",
        manual_parameters=[ # Описываем параметры
             openapi.Parameter('timespan', openapi.IN_QUERY, description="Период (today, week, month, all, etc.)", type=openapi.TYPE_STRING, default='all'),
             # ... другие параметры даты ...
         ]
    )
    def financial_summary(self, request, pk=None):
        """Получение финансовой сводки по магазину с фильтрацией по датам/периодам."""
        # Код метода остается как в предыдущем ответе (с использованием get_date_range_from_params)
        # ...
        store = self.get_object()
        user = request.user
        if not (user.role == 'admin' or store.partner == user): raise PermissionDenied("Нет доступа")
        try: start_date, end_date, selected_timespan_label = get_date_range_from_params(request)
        except serializers.ValidationError as e: return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        # ... (остальной код расчета статистики как был) ...
        # Расчеты и формирование response...
        # Используем Decimal и float() для вывода
        # ...
        # Пример:
        # profit = period_paid_amount - period_partner_expense_amount - period_defect_cost
        # return Response({..., "period_finances": {"profit": float(profit), ...} })
        # Полный код метода financial_summary был в предыдущих ответах
        # Важно: убедись, что он актуален и не содержит ошибок
        # ЗАГЛУШКА - верни сюда актуальный код из предыдущих ответов
        return Response({"detail": "Метод financial_summary еще не полностью скопирован"}) # Заглушка

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def pay_debt(self, request, pk=None):
        """Частичная оплата долга магазина (Админ или Владелец)."""
        store = self.get_object()
        user = request.user
        if not (user.role == 'admin' or (user.role == 'partner' and store.partner == user)):
            raise PermissionDenied("У вас нет прав для добавления оплаты этому магазину")

        if store.remaining_debt <= Decimal('0.00'):
            return Response({"detail": "У магазина нет неоплаченного долга"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = StoreDebtPaymentSerializer(data=request.data, context={'request': request, 'view': self, 'store': store})
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        logger.info(f"Пользователь {user.email} добавил оплату {payment.amount} для магазина {store.name}")
        return Response(StoreDebtPaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def activate(self, request, pk=None):
        """(Админ) Активация магазина (is_active=True)"""
        store = self.get_object()
        if store.is_active: return Response({"detail": "Магазин уже активен"}, status=status.HTTP_400_BAD_REQUEST)
        store.is_active = True; store.save(update_fields=['is_active']); logger.info(f"Админ {request.user.email} активировал магазин {store.name}")
        return Response(StoreSerializer(store, context={'request': request}).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def deactivate(self, request, pk=None):
        """(Админ) Деактивация магазина (is_active=False)"""
        store = self.get_object()
        if not store.is_active: return Response({"detail": "Магазин уже деактивирован"}, status=status.HTTP_400_BAD_REQUEST)
        store.is_active = False; store.save(update_fields=['is_active']); logger.info(f"Админ {request.user.email} деактивировал магазин {store.name}")
        return Response(StoreSerializer(store, context={'request': request}).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsOwnerOrAdmin])
    def soft_delete(self, request, pk=None):
        """(Админ или Владелец) Мягкое удаление магазина"""
        store = self.get_object()
        if store.is_deleted: return Response({"detail": "Магазин уже удален"}, status=status.HTTP_400_BAD_REQUEST)
        if store.soft_delete(): logger.info(f"Пользователь {request.user.email} удалил (мягко) магазин {store.name}"); return Response({"detail": "Магазин успешно помечен как удаленный"}, status=status.HTTP_200_OK)
        else: return Response({"detail": "Не удалось удалить магазин"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def restore(self, request, pk=None):
        """(Админ) Восстановление удаленного магазина"""
        try: store = Store._base_manager.get(pk=pk)
        except Store.DoesNotExist: return Response({"detail": "Магазин не найден"}, status=status.HTTP_404_NOT_FOUND)
        if not store.is_deleted: return Response({"detail": "Магазин не был удален"}, status=status.HTTP_400_BAD_REQUEST)
        if store.restore(): logger.info(f"Админ {request.user.email} восстановил магазин {store.name}"); return Response(StoreSerializer(store, context={'request': request}).data, status=status.HTTP_200_OK)
        else: return Response({"detail": "Не удалось восстановить магазин"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def merge_stores(self, request):
        """(Админ) Слияние магазинов"""
        # Код метода merge_stores остается как в предыдущем ответе
        original_store_id = request.data.get('original_store_id')
        clone_store_id = request.data.get('clone_store_id')
        if not original_store_id or not clone_store_id: return Response({"error": "Необходимо указать original_store_id и clone_store_id"}, status=status.HTTP_400_BAD_REQUEST)
        if original_store_id == clone_store_id: return Response({"error": "ID магазинов не должны совпадать"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            original_store = Store.objects.get(id=original_store_id, is_deleted=False)
            clone_store = Store.objects.get(id=clone_store_id)
            logger.info(f"Слияние магазина ID {clone_store_id} в магазин ID {original_store_id} админом {request.user.email}")
            with transaction.atomic():
                updated_orders = Order.objects.filter(store=clone_store).update(store=original_store); logger.info(f"Перенесено заказов: {updated_orders}")
                updated_debts = StoreDebt.objects.filter(store=clone_store).update(store=original_store); logger.info(f"Перенесено долгов: {updated_debts}")
                updated_payments = StoreDebtPayment.objects.filter(store=clone_store).update(store=original_store); logger.info(f"Перенесено оплат долгов: {updated_payments}")
                # !!! Добавь сюда другие связанные модели !!!
                if not clone_store.is_deleted: clone_store.soft_delete(); logger.info(f"Магазин-клон ID {clone_store_id} помечен как удаленный.")
            return Response({"detail": "Слияние успешно завершено.", "updated_orders": updated_orders, "updated_debts": updated_debts, "updated_payments": updated_payments}, status=status.HTTP_200_OK)
        except Store.DoesNotExist: return Response({"error": "Один или оба магазина не найдены (или оригинал удален)."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e: logger.exception(f"Ошибка слияния магазинов: {e}"); return Response({"error": "Произошла ошибка при слиянии магазинов."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# --- НОВЫЙ ViewSet ---
class StoreDebtPaymentViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с платежами по долгам магазинов
    """
    serializer_class = StoreDebtPaymentSerializer
    permission_classes = [permissions.IsAuthenticated] # Права проверяются в сериализаторе/действиях
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['store', 'store__city', 'store__partner'] # Добавили фильтры
    ordering_fields = ['payment_date', 'amount']
    ordering = ['-payment_date']

    def get_queryset(self):
        user = self.request.user
        queryset = StoreDebtPayment.objects.select_related('store', 'store__partner', 'store__city') # Оптимизация

        if user.role == 'admin':
            return queryset # Админ видит все
        elif user.role == 'partner':
            # Партнер видит платежи только по своим магазинам
            return queryset.filter(store__partner=user)
        else:
            return StoreDebtPayment.objects.none()

    # Переопределяем create, чтобы убедиться, что используется правильный сериализатор и контекст
    def create(self, request, *args, **kwargs):
         serializer = self.get_serializer(data=request.data)
         try:
              serializer.is_valid(raise_exception=True)
              # Сериализатор выполнит проверку прав и суммы
              self.perform_create(serializer)
              headers = self.get_success_headers(serializer.data)
              return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
         except (serializers.ValidationError, PermissionDenied) as e:
              logger.warning(f"Ошибка создания платежа пользователем {request.user.email}: {e}")
              # Возвращаем детали ошибки
              error_detail = e.detail if isinstance(e, serializers.ValidationError) else {"detail": str(e)}
              return Response(error_detail, status=status.HTTP_400_BAD_REQUEST if isinstance(e, serializers.ValidationError) else status.HTTP_403_FORBIDDEN)


    def get_permissions(self):
         # Используем IsOwnerOrAdmin для update/destroy
        if self.action in ['update', 'partial_update', 'destroy']:
             # IsOwnerOrAdmin проверяет поле 'partner' у объекта Store,
             # а у нас объект StoreDebtPayment. Нужно кастомное разрешение или проверка в методе.
             # Проще всего проверить в самом методе perform_update/perform_destroy.
             # Пока оставим общее разрешение, но помним об этом.
             # return [IsOwnerOrAdmin()] # НЕПРАВИЛЬНО для StoreDebtPayment
             return [permissions.IsAuthenticated()] # Проверку сделаем ниже
        return [permissions.IsAuthenticated()]

    def perform_update(self, serializer):
         # Проверка прав перед обновлением
         instance = serializer.instance
         user = self.request.user
         if not (user.role == 'admin' or instance.store.partner == user):
              raise PermissionDenied("У вас нет прав изменять этот платеж.")
         # Не позволяем менять сумму или магазин после создания
         if 'amount' in serializer.validated_data and serializer.validated_data['amount'] != instance.amount:
             raise serializers.ValidationError({"amount": "Нельзя изменить сумму существующего платежа."})
         if 'store' in serializer.validated_data and serializer.validated_data['store'] != instance.store:
              raise serializers.ValidationError({"store": "Нельзя изменить магазин для существующего платежа."})
         serializer.save()

    def perform_destroy(self, instance):
         # Проверка прав перед удалением
         user = self.request.user
         if not (user.role == 'admin' or instance.store.partner == user):
              raise PermissionDenied("У вас нет прав удалять этот платеж.")
         logger.warning(f"Пользователь {user.email} удаляет платеж ID {instance.id} магазина {instance.store.name} на сумму {instance.amount}.")
         instance.delete()



class StoreDebtViewSet(viewsets.ModelViewSet):
     serializer_class = StoreDebtSerializer
     permission_classes = [permissions.IsAuthenticated] # Уточнить права
     filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
     filterset_fields = ['store', 'is_paid', 'store__city', 'store__partner']
     ordering_fields = ['amount', 'created_at']
     ordering = ['-created_at']

     def get_queryset(self):
         user = self.request.user
         queryset = StoreDebt.objects.select_related('store')
         if user.role == 'admin':
             return queryset
         elif user.role == 'partner':
             return queryset.filter(store__partner=user)
         return StoreDebt.objects.none()

     def get_permissions(self):
         if self.action in ['update', 'partial_update', 'destroy']:
             # return [IsOwnerOrAdmin()] # Неправильно, нужно проверять store.partner
             return [permissions.IsAuthenticated()] # Проверку делать в методах
         return [permissions.IsAuthenticated()]

     def perform_update(self, serializer):
         instance = serializer.instance
         user = self.request.user
         if not (user.role == 'admin' or instance.store.partner == user):
             raise PermissionDenied("У вас нет прав изменять этот долг.")
         # Запретить изменение суммы или магазина?
         if 'amount' in serializer.validated_data and serializer.validated_data['amount'] != instance.amount:
             raise serializers.ValidationError({"amount": "Нельзя изменить сумму существующего долга."})
         if 'store' in serializer.validated_data and serializer.validated_data['store'] != instance.store:
             raise serializers.ValidationError({"store": "Нельзя изменить магазин для существующего долга."})
         serializer.save()

     def perform_destroy(self, instance):
         user = self.request.user
         if not (user.role == 'admin' or instance.store.partner == user):
             raise PermissionDenied("У вас нет прав удалять этот долг.")
         # Подумать, нужно ли удалять долги или только помечать?
         logger.warning(f"Пользователь {user.email} удаляет долг ID {instance.id} магазина {instance.store.name} на сумму {instance.amount}.")
         instance.delete()

     @action(detail=True, methods=['post'])
     def mark_paid(self, request, pk=None):
          # Логика из старого ViewSet'а
          debt = self.get_object()
          user = request.user
          if not (user.role == 'admin' or debt.store.partner == user):
               raise PermissionDenied("У вас нет прав для выполнения этого действия")

          if debt.is_paid:
               return Response({"detail": "Долг уже оплачен"}, status=status.HTTP_400_BAD_REQUEST)

          # Создаем платеж на ПОЛНУЮ ОСТАВШУЮСЯ сумму долга
          # Или на всю сумму долга, если платежей не было?
          # Лучше создавать платеж на конкретную сумму через StoreDebtPaymentViewSet
          # Этот action может быть просто для пометки is_paid=True
          debt.is_paid = True
          debt.save(update_fields=['is_paid'])
          logger.info(f"Пользователь {user.email} отметил долг ID {debt.id} как оплаченный.")
          return Response({"detail": "Долг успешно отмечен как оплаченный"}, status=status.HTTP_200_OK)

     @action(detail=False, methods=['get'])
     def store_debts(self, request):
         # Логика из старого ViewSet'а
         store_id = request.query_params.get('store_id')
         if not store_id:
             return Response({"detail": "Необходимо указать ID магазина"}, status=status.HTTP_400_BAD_REQUEST)

         # Проверка доступа к магазину
         user = request.user
         try:
             store = Store.objects.get(id=store_id)
             if not (user.role == 'admin' or store.partner == user):
                 raise PermissionDenied("У вас нет доступа к этому магазину")
         except Store.DoesNotExist:
             return Response({"detail": "Магазин не найден"}, status=status.HTTP_404_NOT_FOUND)
         except PermissionDenied as e:
              return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)


         queryset = self.get_queryset().filter(store_id=store_id)
         is_paid = request.query_params.get('is_paid')
         if is_paid is not None:
             is_paid_bool = is_paid.lower() == 'true'
             queryset = queryset.filter(is_paid=is_paid_bool)

         serializer = StoreDebtSerializer(queryset, many=True)
         total_amount = queryset.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

         return Response({
             "store_id": store_id,
             "store_name": store.name,
             "debts": serializer.data,
             "total_amount": float(total_amount),
             "count": queryset.count()
         })


class StoresSummaryStatisticsView(APIView):
    """
    Представление для получения агрегированной статистики по группе магазинов.
    Админ видит статистику по всем магазинам (или отфильтрованным).
    Партнер видит статистику только по своим магазинам.
    """
    permission_classes = [permissions.IsAuthenticated] # Доступ по роли проверяется внутри

    @swagger_auto_schema(
        operation_summary="Сводная статистика по магазинам",
        manual_parameters=[
             openapi.Parameter('timespan', openapi.IN_QUERY, description="Период (today, yesterday, week, ..., all)", type=openapi.TYPE_STRING, default='all'),
             openapi.Parameter('date', openapi.IN_QUERY, description="Дата (YYYY-MM-DD)", type=openapi.TYPE_STRING, format='date'),
             openapi.Parameter('start_date', openapi.IN_QUERY, description="Начальная дата (YYYY-MM-DD)", type=openapi.TYPE_STRING, format='date'),
             openapi.Parameter('end_date', openapi.IN_QUERY, description="Конечная дата (YYYY-MM-DD)", type=openapi.TYPE_STRING, format='date'),
             openapi.Parameter('city_id', openapi.IN_QUERY, description="Фильтр по ID города", type=openapi.TYPE_INTEGER),
             openapi.Parameter('partner_id', openapi.IN_QUERY, description="Фильтр по ID партнера (только для админа)", type=openapi.TYPE_INTEGER),
        ]
    )
    def get(self, request):
        user = request.user
        city_id = request.query_params.get('city_id')
        partner_id = request.query_params.get('partner_id')

        # Проверка partner_id для админа
        if user.role != 'admin' and partner_id:
             return Response({"detail": "Фильтр по партнеру доступен только администратору."}, status=status.HTTP_403_FORBIDDEN)

        try:
            start_date, end_date, selected_timespan = get_date_range_from_params(request)
        except serializers.ValidationError as e:
             return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        service = StoreGroupStatisticsService()
        statistics = service.get_stores_statistics(
            user=user, # Передаем пользователя для проверки прав
            date_range=(start_date, end_date),
            city_id=city_id,
            partner_id=partner_id
        )

        if "error" in statistics:
            status_code = status.HTTP_403_FORBIDDEN if statistics["error"] == "Доступ запрещен" else status.HTTP_404_NOT_FOUND
            return Response({"detail": statistics["error"]}, status=status_code)

        statistics["selected_timespan"] = selected_timespan
        return Response(statistics)