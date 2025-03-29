from django.db.models import Q
from drf_yasg.utils import swagger_auto_schema
from rest_framework import viewsets, permissions
from rest_framework.views import APIView

from .models import Message
from .serializers import MessageSerializer
from apps.users.models import  User
from apps.stores.models import Store
from drf_yasg import openapi
from rest_framework.response import Response


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Message.objects.filter(sender=user) | Message.objects.filter(receiver=user)

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)


# Добавить новое представление
class PartnerChatListView(APIView):
    permission_classes = [permissions.IsAdminUser]

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
        # Получаем параметры фильтрации
        city_id = request.query_params.get('city')
        search = request.query_params.get('search', '')

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
            from apps.orders.models import ProductRequest
            # Находим партнеров, работающих с магазинами в этом городе
            store_ids = Store.objects.filter(city_id=city_id).values_list('id', flat=True)
            partner_ids = ProductRequest.objects.filter(
                store_id__in=store_ids
            ).values_list('user_id', flat=True).distinct()
            partners = partners.filter(id__in=partner_ids)

        # Получаем последнее сообщение для каждого партнера
        result = []
        for partner in partners:
            # Ищем последнее сообщение с этим партнером (отправленное или полученное)
            latest_message = Message.objects.filter(
                Q(sender=partner, receiver=request.user) |
                Q(sender=request.user, receiver=partner)
            ).order_by('-timestamp').first()

            # Формируем информацию о чате
            chat_info = {
                "partner_id": partner.id,
                "partner_name": f"{partner.first_name} {partner.last_name}",
                "partner_email": partner.email,
                "partner_photo": request.build_absolute_uri(partner.photo.url) if partner.photo else None,
                "unread_count": Message.objects.filter(
                    sender=partner,
                    receiver=request.user,
                    is_read=False
                ).count()
            }

            # Добавляем информацию о последнем сообщении, если оно есть
            if latest_message:
                chat_info.update({
                    "last_message": {
                        "id": latest_message.id,
                        "text": latest_message.text[:100] + "..." if len(
                            latest_message.text or "") > 100 else latest_message.text,
                        "timestamp": latest_message.timestamp.isoformat(),
                        "is_from_me": latest_message.sender == request.user
                    }
                })

            result.append(chat_info)

        # Сортируем по наличию непрочитанных и времени последнего сообщения
        result.sort(key=lambda x: (
            -x.get("unread_count", 0),
            x.get("last_message", {}).get("timestamp", "0") if x.get("last_message") else "0"
        ), reverse=True)

        return Response(result)