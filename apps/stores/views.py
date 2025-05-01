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


class StoreViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с магазинами
    """
    serializer_class = StoreSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['city', 'status', 'is_active', 'partner'] # Добавили is_active, partner
    search_fields = ['name', 'inn', 'address', 'phone', 'partner__first_name', 'partner__last_name', 'partner__email'] # Добавили phone, partner
    ordering_fields = ['name', 'created_at', 'city__name', 'partner__last_name'] # Добавили city, partner
    ordering = ['name'] # Сортировка по умолчанию

    def get_queryset(self):
        user = self.request.user
        # Показываем только НЕ удаленные магазины по умолчанию
        queryset = Store.objects.filter(is_deleted=False).select_related('city', 'partner')

        if user.role == 'admin':
             # Админ видит все неудаленные магазины
             pass # queryset уже отфильтрован
        elif user.role == 'partner':
             # Партнер видит только СВОИ неудаленные магазины
             queryset = queryset.filter(partner=user)
        else:
             # Другие роли (если появятся) ничего не видят
             queryset = Store.objects.none()

        # Позволяем админу видеть удаленные, если запрошено
        is_deleted_param = self.request.query_params.get('is_deleted')
        if user.role == 'admin' and is_deleted_param is not None:
            show_deleted = is_deleted_param.lower() == 'true'
            if show_deleted:
                 # Переопределяем queryset, чтобы показать удаленные
                 queryset = Store.objects.filter(is_deleted=True).select_related('city', 'partner')

        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return StoreListSerializer
        return StoreSerializer

    def get_permissions(self):
        if self.action == 'create':
            # Партнеры и админы могут создавать
            return [permissions.IsAuthenticated()] # Проверка роли будет ниже
        elif self.action in ['update', 'partial_update']:
            # Только владелец или админ
            return [IsOwnerOrAdmin()]
        elif self.action == 'destroy':
             # Только админ может жестко удалить (не рекомендуется)
             # Для мягкого удаления используется soft_delete action
            return [IsAdminUser()]
        # Для actions права определяются в декораторе
        return [permissions.IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        user = request.user
        if user.role == 'admin':
            # Админ должен указать партнера в запросе
            if 'partner' not in request.data:
                 return Response({"partner": ["Это поле обязательно для администратора."]}, status=status.HTTP_400_BAD_REQUEST)
            # Валидация партнера будет в сериализаторе
        elif user.role == 'partner':
            # Партнер создает магазин для себя
            request.data['partner'] = user.id
        else:
            # Другие роли не могут создавать магазины
            return Response({"detail": "У вас нет прав для создания магазина"}, status=status.HTTP_403_FORBIDDEN)

        # Статус и is_deleted устанавливаются в сериализаторе
        # request.data['status'] = 'approved'
        # request.data['is_deleted'] = False
        return super().create(request, *args, **kwargs)

    # УДАЛЯЕМ устаревшие actions approve, reject, pending
    # @action(detail=True, methods=['post'])
    # def approve(self, request, pk=None): ...
    # @action(detail=True, methods=['post'])
    # def reject(self, request, pk=None): ...
    # @action(detail=False, methods=['get'])
    # def pending(self, request): ...

    @action(detail=False, methods=['get'])
    def with_debt(self, request):
        """Получение списка магазинов с долгами"""
        # Оптимизированный запрос с аннотацией
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
    @swagger_auto_schema(  # Добавим документацию для параметров даты
        operation_summary="Финансовая сводка по магазину",
        manual_parameters=[
            openapi.Parameter('timespan', openapi.IN_QUERY,
                              description="Период (today, yesterday, week, month, six_months, year, last_year, all)",
                              type=openapi.TYPE_STRING),
            openapi.Parameter('date', openapi.IN_QUERY, description="Конкретная дата (YYYY-MM-DD)",
                              type=openapi.TYPE_STRING, format='date'),
            openapi.Parameter('start_date', openapi.IN_QUERY, description="Начальная дата (YYYY-MM-DD)",
                              type=openapi.TYPE_STRING, format='date'),
            openapi.Parameter('end_date', openapi.IN_QUERY, description="Конечная дата (YYYY-MM-DD)",
                              type=openapi.TYPE_STRING, format='date'),
            openapi.Parameter('period', openapi.IN_QUERY, description="Старый параметр периода (this_week и т.д.)",
                              type=openapi.TYPE_STRING),
        ]
    )
    def financial_summary(self, request, pk=None):
        """
        Получение финансовой сводки по магазину с возможностью фильтрации по датам/периодам.
        """
        store = self.get_object()
        user = request.user

        if not (user.role == 'admin' or store.partner == user):
            raise PermissionDenied("У вас нет доступа к этому магазину")

        # --- ИСПОЛЬЗУЕМ ХЕЛПЕР ДЛЯ ДАТ ---
        try:
            # Импортируем хелпер
            from apps.finance.views import get_date_range_from_params
            start_date, end_date, selected_timespan_label = get_date_range_from_params(request)
        except serializers.ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        except ImportError:
            # Fallback, если хелпер не найден (хотя должен быть)
            logger.error("Хелпер get_date_range_from_params не найден в finance.views")
            return Response({"error": "Ошибка конфигурации сервера."}, status=500)
        # --- КОНЕЦ ИСПОЛЬЗОВАНИЯ ХЕЛПЕРА ---

        # Получаем данные за период (start_date, end_date)
        from apps.orders.models import Order, OrderItem, DefectItem
        from apps.finance.models import PartnerExpense

        # Заказы магазина за период
        period_orders = Order.objects.filter(
            store=store,
            order_type='partner_to_store',
            status='confirmed',
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).prefetch_related('order_items', 'order_items__product', 'defect_items',
                           'defect_items__product')  # Оптимизация

        # Элементы этих заказов (уже предзагружены)
        period_order_items_list = [item for order in period_orders for item in order.order_items.all()]

        # Долги магазина за период
        period_debts = StoreDebt.objects.filter(
            store=store,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )

        # Платежи магазина за период
        period_payments = StoreDebtPayment.objects.filter(
            store=store,
            payment_date__date__gte=start_date,
            payment_date__date__lte=end_date
        )

        # Расходы ПАРТНЕРА за период (владельца магазина)
        partner_expenses = PartnerExpense.objects.filter(
            partner=store.partner,
            expense_date__gte=start_date,
            expense_date__lte=end_date
        )

        # Брак в заказах магазина за период (уже предзагружен)
        period_defects_list = [defect for order in period_orders for defect in order.defect_items.all()]

        # --- РАСЧЕТЫ (как были, но используем Decimal) ---
        total_debt_all_time = store.total_debt
        total_paid_all_time = store.total_paid_debt
        remaining_debt_all_time = store.remaining_debt

        period_debt_amount = period_debts.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        period_paid_amount = period_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        period_partner_expense_amount = partner_expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        period_ordered_quantity = sum(item.quantity for item in period_order_items_list)
        period_bonus_quantity = sum(item.bonus_quantity or 0 for item in period_order_items_list)
        period_defect_quantity = sum(defect.quantity for defect in period_defects_list)

        period_sales_amount = sum(item.total_price for item in period_order_items_list)
        period_defect_cost = sum(defect.total_price for defect in period_defects_list)

        # Прибыль партнера от этого магазина за период = ОплатыМагазина - РасходыПартнера(?) - СтоимостьБрака
        profit = period_paid_amount - period_partner_expense_amount - period_defect_cost

        # Детализация по товарам
        products_summary = {}
        for item in period_order_items_list:
            product_id = item.product_id
            # Используем get для инициализации
            summary = products_summary.setdefault(product_id, {
                "product_id": product_id, "product_name": item.product.name, "quantity": 0,
                "bonus_quantity": 0, "defect_quantity": 0, "price": float(item.price),
                "total_sold_price": 0.0
            })
            summary['quantity'] += item.quantity
            summary['bonus_quantity'] += (item.bonus_quantity or 0)
            summary['total_sold_price'] += float(item.total_price)

        for defect in period_defects_list:
            product_id = defect.product_id
            summary = products_summary.setdefault(product_id, {
                "product_id": product_id, "product_name": defect.product.name, "quantity": 0,
                "bonus_quantity": 0, "defect_quantity": 0, "price": float(defect.product.price),
                "total_sold_price": 0.0
            })
            summary['defect_quantity'] += defect.quantity

        # --- ФОРМИРОВАНИЕ ОТВЕТА (как был, но используем float() для Decimal) ---
        return Response({
            "store_id": store.id,
            "store_name": store.name,
            # ... (остальные поля) ...
            "date_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "selected_timespan": selected_timespan_label,  # Добавляем метку
                "formatted": start_date.strftime(
                    "%d.%m.%Y") if start_date == end_date else f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
            },
            "overall_finances": {
                "total_debt": float(total_debt_all_time),
                "total_paid": float(total_paid_all_time),
                "remaining_debt": float(remaining_debt_all_time),
            },
            "period_finances": {
                "sales_amount": float(period_sales_amount),
                "paid_amount": float(period_paid_amount),
                "debt_created": float(period_debt_amount),
                "partner_expenses": float(period_partner_expense_amount),
                "defect_cost": float(period_defect_cost),
                "profit": float(profit),
            },
            # ... (period_items и products_summary) ...
            "period_items": {
                "orders_count": period_orders.count(),
                "ordered_quantity": period_ordered_quantity,
                "bonus_quantity": period_bonus_quantity,
                "defect_quantity": period_defect_quantity,
            },
            "products_summary": list(products_summary.values())
        })

    @action(detail=False, methods=['get'])
    def stores_summary(self, request):
        # Этот метод стал слишком сложным и дублирует логику
        # financial_summary и Partner/AdminStatisticsService.
        # Предлагаю его УПРОСТИТЬ до простого списка магазинов с базовой инфой.
        # Статистику по группам лучше получать через AdminPartnersStatisticsView
        user = request.user
        queryset = self.get_queryset() # Уже учитывает роль и is_deleted

        # Применяем стандартные фильтры DRF
        queryset = self.filter_queryset(queryset)

        serializer = StoreListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def city_summary(self, request):
        # Аналогично stores_summary, упрощаем
        city_id = request.query_params.get('city_id')
        if not city_id:
             return Response({"detail": "Параметр city_id обязателен"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            city = City.objects.get(id=city_id)
        except City.DoesNotExist:
             return Response({"detail": "Город не найден"}, status=status.HTTP_404_NOT_FOUND)

        queryset = self.get_queryset().filter(city=city) # Фильтруем по городу
        queryset = self.filter_queryset(queryset) # Применяем остальные фильтры

        serializer = StoreListSerializer(queryset, many=True, context={'request': request})
        return Response({
            "city": {"id": city.id, "name": city.name},
            "stores": serializer.data
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated]) # Проверка прав внутри
    def add_expense(self, request, pk=None):
        """Добавление расхода для ПАРТНЕРА (НЕ для магазина)"""
        # Этот метод больше не относится к расходам магазина.
        # Его нужно либо удалить, либо переделать для добавления PartnerExpense,
        # но лучше использовать PartnerExpenseViewSet.
        # Пока возвращаем ошибку.
        return Response(
            {"detail": "Эта функция устарела. Используйте /api/finance/partner-expenses/ для добавления расходов партнера."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )


    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated]) # Проверка прав внутри
    def pay_debt(self, request, pk=None):
        """Частичная оплата долга магазина"""
        store = self.get_object() # Получаем магазин (права проверены в get_object)
        user = request.user

        # Проверка прав доступа (повторно, для надежности)
        if not (user.role == 'admin' or (user.role == 'partner' and store.partner == user)):
            raise PermissionDenied("У вас нет прав для добавления оплаты этому магазину")

        # Проверяем, что у магазина есть долг
        if store.remaining_debt <= Decimal('0.00'):
            return Response({"detail": "У магазина нет неоплаченного долга"}, status=status.HTTP_400_BAD_REQUEST)

        # Используем сериализатор для валидации и создания платежа
        # Передаем store в контексте, если он не передается в data
        serializer = StoreDebtPaymentSerializer(
            data=request.data,
            context={'request': request, 'view': self, 'store': store} # Добавляем store в контекст
        )

        serializer.is_valid(raise_exception=True)
        payment = serializer.save() # Сериализатор проверит права и сумму

        # StoreDebtPayment.save() обновит статусы долгов, если нужно
        logger.info(f"Пользователь {user.email} добавил оплату {payment.amount} для магазина {store.name}")

        # Возвращаем данные созданного платежа
        return Response(
            StoreDebtPaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def activate(self, request, pk=None):
        """Активация магазина"""
        store = self.get_object() # Получаем только неудаленные
        if store.is_active:
            return Response({"detail": "Магазин уже активен"}, status=status.HTTP_400_BAD_REQUEST)
        store.is_active = True
        store.save(update_fields=['is_active'])
        logger.info(f"Администратор {request.user.email} активировал магазин {store.name}")
        return Response(StoreSerializer(store).data, status=status.HTTP_200_OK) # Возвращаем данные

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def deactivate(self, request, pk=None):
        """Деактивация магазина"""
        store = self.get_object() # Получаем только неудаленные
        if not store.is_active:
            return Response({"detail": "Магазин уже деактивирован"}, status=status.HTTP_400_BAD_REQUEST)
        store.is_active = False
        store.save(update_fields=['is_active'])
        logger.info(f"Администратор {request.user.email} деактивировал магазин {store.name}")
        return Response(StoreSerializer(store).data, status=status.HTTP_200_OK) # Возвращаем данные

    @action(detail=True, methods=['post'], permission_classes=[IsOwnerOrAdmin]) # Владелец или админ
    def soft_delete(self, request, pk=None):
        """Мягкое удаление магазина"""
        store = self.get_object() # Получаем только неудаленные
        if store.is_deleted: # На всякий случай
             return Response({"detail": "Магазин уже удален"}, status=status.HTTP_400_BAD_REQUEST)

        if store.soft_delete():
             logger.info(f"Пользователь {request.user.email} удалил (мягко) магазин {store.name}")
             return Response({"detail": "Магазин успешно помечен как удаленный"}, status=status.HTTP_200_OK)
        else:
             return Response({"detail": "Не удалось удалить магазин"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser]) # Только админ
    def restore(self, request, pk=None):
        """Восстановление удаленного магазина"""
        try:
             # Используем _base_manager для поиска среди всех, включая удаленные
            store = Store._base_manager.get(pk=pk)
        except Store.DoesNotExist:
            return Response({"detail": "Магазин не найден"}, status=status.HTTP_404_NOT_FOUND)

        if not store.is_deleted:
            return Response({"detail": "Магазин не был удален"}, status=status.HTTP_400_BAD_REQUEST)

        if store.restore():
            logger.info(f"Администратор {request.user.email} восстановил магазин {store.name}")
            return Response(StoreSerializer(store).data, status=status.HTTP_200_OK) # Возвращаем данные
        else:
             return Response({"detail": "Не удалось восстановить магазин"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # --- НОВЫЙ ACTION ДЛЯ СЛИЯНИЯ ---
    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def merge_stores(self, request):
        original_store_id = request.data.get('original_store_id')
        clone_store_id = request.data.get('clone_store_id')

        if not original_store_id or not clone_store_id:
            return Response({"error": "Необходимо указать original_store_id и clone_store_id"}, status=status.HTTP_400_BAD_REQUEST)

        if original_store_id == clone_store_id:
            return Response({"error": "ID магазинов не должны совпадать"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Получаем оба магазина
            original_store = Store.objects.get(id=original_store_id, is_deleted=False) # Оригинал должен быть не удален
            clone_store = Store.objects.get(id=clone_store_id) # Клон может быть удален

            logger.info(f"Начало слияния магазина ID {clone_store_id} в магазин ID {original_store_id} админом {request.user.email}")

            with transaction.atomic():
                # 1. Перепривязываем заказы
                from apps.orders.models import Order
                updated_orders = Order.objects.filter(store=clone_store).update(store=original_store)
                logger.info(f"Перенесено заказов: {updated_orders}")

                # 2. Перепривязываем долги
                updated_debts = StoreDebt.objects.filter(store=clone_store).update(store=original_store)
                logger.info(f"Перенесено долгов: {updated_debts}")

                # 3. Перепривязываем оплаты долгов
                updated_payments = StoreDebtPayment.objects.filter(store=clone_store).update(store=original_store)
                logger.info(f"Перенесено оплат долгов: {updated_payments}")

                # 4. TODO: Перепривязать ДРУГИЕ СВЯЗАННЫЕ МОДЕЛИ (если есть)
                # Например, статистика, если она связана с магазином напрямую
                # DailyStatistics.objects.filter(store=clone_store).update(store=original_store)

                # 5. Мягкое удаление клона (если еще не удален)
                if not clone_store.is_deleted:
                    clone_store.soft_delete()
                    logger.info(f"Магазин-клон ID {clone_store_id} помечен как удаленный.")
                else:
                    logger.info(f"Магазин-клон ID {clone_store_id} уже был удален.")

            logger.info(f"Слияние магазина ID {clone_store_id} в магазин ID {original_store_id} успешно завершено.")
            return Response({
                "detail": f"Данные магазина ID {clone_store_id} успешно перенесены в магазин ID {original_store_id}. Клон помечен как удаленный.",
                "updated_orders": updated_orders,
                "updated_debts": updated_debts,
                "updated_payments": updated_payments,
                # Добавить счетчики для других моделей
            }, status=status.HTTP_200_OK)

        except Store.DoesNotExist:
            return Response({"error": "Один или оба магазина не найдены (или оригинал удален)."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(f"Ошибка слияния магазинов: {e}")
            return Response({"error": "Произошла ошибка при слиянии магазинов."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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