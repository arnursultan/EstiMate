from django.db.models import Q, Count, Max, OuterRef, Subquery
from rest_framework import viewsets, permissions, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Message
from .serializers import MessageSerializer
import logging

logger = logging.getLogger(__name__)


class IsAdminUser(permissions.BasePermission):
    """Разрешение только для администраторов"""

    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class MessageViewSet(viewsets.ModelViewSet):
    """API для работы с сообщениями"""
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['is_read']
    ordering_fields = ['timestamp']
    ordering = ['timestamp']

    def get_queryset(self):
        """
        Возвращает сообщения, связанные с текущим пользователем.
        Для Swagger возвращает пустой QuerySet.
        """
        if getattr(self, 'swagger_fake_view', False):
            return Message.objects.none()

        user = self.request.user

        # Получаем собеседника, если указан
        partner_id = self.request.query_params.get('partner')

        if partner_id:
            # Сообщения между текущим пользователем и конкретным партнером
            return Message.objects.filter(
                (Q(sender=user) & Q(receiver_id=partner_id)) |
                (Q(receiver=user) & Q(sender_id=partner_id))
            ).order_by('timestamp')
        else:
            # Все сообщения, связанные с текущим пользователем
            return Message.objects.filter(
                Q(sender=user) | Q(receiver=user)
            ).order_by('timestamp')

    def perform_create(self, serializer):
        """Создание сообщения от имени текущего пользователя"""
        serializer.save(sender=self.request.user)

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Отметить сообщение как прочитанное"""
        message = self.get_object()

        # Только получатель может отметить сообщение как прочитанное
        if message.receiver != request.user:
            return Response(
                {"error": "Вы можете отметить как прочитанное только ваше сообщение"},
                status=status.HTTP_403_FORBIDDEN
            )

        if message.is_read:
            return Response(
                {"message": "Сообщение уже отмечено как прочитанное"},
                status=status.HTTP_200_OK
            )

        message.mark_as_read()
        serializer = self.get_serializer(message)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Отметить все сообщения как прочитанные"""
        # Обновляем только сообщения, где текущий пользователь является получателем
        messages = Message.objects.filter(receiver=request.user, is_read=False)
        updated_count = messages.update(is_read=True)

        return Response({
            "message": f"Отмечено как прочитанные {updated_count} сообщений",
            "updated_count": updated_count
        })

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Получить количество непрочитанных сообщений"""
        count = Message.objects.filter(receiver=request.user, is_read=False).count()
        return Response({"unread_count": count})


class PartnerChatListView(APIView):
    """API для получения списка партнеров для чата (только для администраторов)"""
    permission_classes = [IsAdminUser]

    @swagger_auto_schema(
        operation_summary="Список чатов с партнерами",
        operation_description="Возвращает список партнеров для чата с основной информацией",
        manual_parameters=[
            openapi.Parameter(
                'city',
                openapi.IN_QUERY,
                description="ID города для фильтрации",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'search',
                openapi.IN_QUERY,
                description="Поиск по имени, фамилии или email",
                type=openapi.TYPE_STRING
            )
        ]
    )
    def get(self, request):
        if getattr(self, 'swagger_fake_view', False):
            return Response([])

        try:
            # Получаем параметры фильтрации
            city_id = request.query_params.get('city')
            search = request.query_params.get('search', '')

            # Импортируем модели здесь, чтобы избежать проблем с AppRegistry
            from django.contrib.auth import get_user_model
            User = get_user_model()
            from apps.stores.models import Store

            # Основной запрос - все партнеры
            partners = User.objects.filter(is_staff=False, is_active=True)

            # Применяем фильтры
            if search:
                partners = partners.filter(
                    Q(email__icontains=search) |
                    Q(first_name__icontains=search) |
                    Q(last_name__icontains=search)
                )

            # Если нужно фильтровать по городу
            if city_id:
                # Находим партнеров, работающих с магазинами в этом городе
                from apps.orders.models import ProductRequest
                store_ids = Store.objects.filter(city_id=city_id).values_list('id', flat=True)
                partner_ids = ProductRequest.objects.filter(
                    store_id__in=store_ids
                ).values_list('user_id', flat=True).distinct()
                partners = partners.filter(id__in=partner_ids)

            # Подзапрос для последнего сообщения
            latest_message_subquery = Message.objects.filter(
                (Q(sender=OuterRef('pk')) & Q(receiver=request.user)) |
                (Q(receiver=OuterRef('pk')) & Q(sender=request.user))
            ).order_by('-timestamp').values('timestamp')[:1]

            # Подзапрос для количества непрочитанных сообщений
            unread_count_subquery = Message.objects.filter(
                sender=OuterRef('pk'),
                receiver=request.user,
                is_read=False
            ).values('sender').annotate(count=Count('id')).values('count')

            # Применяем подзапросы к основному запросу
            partners = partners.annotate(
                last_message_time=Subquery(latest_message_subquery),
                unread_count=Subquery(unread_count_subquery, output_field=Count('id'))
            )

            # Сортируем по наличию непрочитанных и времени последнего сообщения
            partners = partners.order_by('-unread_count', '-last_message_time')

            # Формируем результат
            result = []
            for partner in partners:
                # Ищем последнее сообщение с этим партнером (отправленное или полученное)
                latest_message = Message.objects.filter(
                    (Q(sender=partner, receiver=request.user)) |
                    (Q(receiver=partner, sender=request.user))
                ).order_by('-timestamp').first()

                # Формируем информацию о чате
                chat_info = {
                    "partner_id": partner.id,
                    "partner_name": f"{partner.first_name} {partner.last_name}",
                    "partner_email": partner.email,
                    "partner_photo": request.build_absolute_uri(partner.photo.url) if partner.photo and hasattr(
                        partner.photo, 'url') else None,
                    "unread_count": Message.objects.filter(
                        sender=partner,
                        receiver=request.user,
                        is_read=False
                    ).count()
                }

                # Добавляем информацию о последнем сообщении, если оно есть
                if latest_message:
                    # Безопасное получение текста сообщения
                    message_text = latest_message.text or ""
                    chat_info.update({
                        "last_message": {
                            "id": latest_message.id,
                            "text": message_text[:100] + "..." if len(message_text) > 100 else message_text,
                            "timestamp": latest_message.timestamp.isoformat(),
                            "is_from_me": latest_message.sender == request.user
                        }
                    })

                result.append(chat_info)

            return Response(result)

        except Exception as e:
            logger.error(f"Ошибка при получении списка чатов: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)