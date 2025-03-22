from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Application
from .serializers import ApplicationSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import IsAdminUser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi


class ApplicationCreateAPIView(APIView):
    """
    Создание заявки на создание магазина.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["full_name", "phone_number", "inn", "city", "address", "title"],
            properties={
                "full_name": openapi.Schema(type=openapi.TYPE_STRING, description="ФИО владельца", maxLength=255),
                "phone_number": openapi.Schema(type=openapi.TYPE_STRING, description="Телефон владельца", maxLength=13),
                "inn": openapi.Schema(type=openapi.TYPE_STRING, description="ИНН магазина", maxLength=14),
                "city": openapi.Schema(type=openapi.TYPE_STRING, description="Город", maxLength=50),
                "address": openapi.Schema(type=openapi.TYPE_STRING, description="Адрес магазина", maxLength=255),
                "title": openapi.Schema(type=openapi.TYPE_STRING, description="Название магазина", maxLength=255),
            },
        ),
        responses={
            201: ApplicationSerializer(),
            400: openapi.Response(
                description="Ошибки валидации данных",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(type=openapi.TYPE_STRING),
                        'errors': openapi.Schema(type=openapi.TYPE_OBJECT)
                    }
                )
            )
        }
    )
    def post(self, request, *args, **kwargs):
        """
        Создание заявки на создание магазина.
        """
        # Добавляем информацию о текущем пользователе в контекст сериализатора
        serializer = ApplicationSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            # Привязываем заявку к текущему пользователю
            application = serializer.save(owner=request.user)  # Здесь устанавливаем владельца заявки

            return Response(
                ApplicationSerializer(application).data,
                status=status.HTTP_201_CREATED
            )
        return Response(
            {"detail": "Ошибка валидации данных", "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )




class ApplicationListAPIView(APIView):
    """
    Просмотр заявок.
    Админ видит все, партнер — только свои.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Получить заявки. Админ видит все, партнер — только свои.",
        responses={
            200: ApplicationSerializer(many=True),
            400: openapi.Response(
                description="Ошибки валидации данных",
                schema=openapi.Schema(type=openapi.TYPE_OBJECT)
            )
        }
    )
    def get(self, request, *args, **kwargs):
        """
        Получить заявки.
        Админ видит все заявки, партнер — только свои.
        """
        if request.user.is_staff:
            applications = Application.objects.all()
        else:
            applications = Application.objects.filter(owner=request.user)

        serializer = ApplicationSerializer(applications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)




class ApplicationDeleteAPIView(APIView):
    """
    Удаление заявки.
    Только админ или владелец заявки может удалить заявку.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Удалить заявку по ID. Только администратор или владелец заявки может удалить заявку.",
        responses={
            204: openapi.Response(
                description="Заявка успешно удалена.",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            404: openapi.Response(
                description="Заявка не найдена.",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            401: openapi.Response(
                description="Не авторизован",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            403: openapi.Response(
                description="Запрещено",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            )
        }
    )
    def delete(self, request, pk, *args, **kwargs):
        """
        Удалить заявку по id (pk).
        """
        try:
            application = Application.objects.get(pk=pk)

            if application.owner != request.user and not request.user.is_staff:
                return Response({"detail": "У вас нет прав для удаления этой заявки."},
                                status=status.HTTP_403_FORBIDDEN)

            application.delete()
            return Response({"detail": "Заявка успешно удалена."}, status=status.HTTP_204_NO_CONTENT)
        except Application.DoesNotExist:
            return Response(
                {"detail": "Заявка не найдена."},
                status=status.HTTP_404_NOT_FOUND
            )

class ApplicationActionAPIView(APIView):
    """
    Подтверждение или отклонение заявки.
    """
    permission_classes = [IsAdminUser]

    @swagger_auto_schema(
        operation_description="Подтвердить или отклонить заявку.",
        responses={
            200: ApplicationSerializer(),
            404: openapi.Response(
                description="Заявка не найдена.",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            401: openapi.Response(
                description="Не авторизован",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            400: openapi.Response(
                description="Неверные параметры запроса",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            )
        }
    )
    def post(self, request, *args, **kwargs):
        """
        Подтвердить или отклонить заявку по ID (pk).
        """
        pk = kwargs.get('pk')
        action = kwargs.get('action')

        if not pk or not action:
            return Response({"detail": "Не переданы параметры."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            application = Application.objects.get(pk=pk)
            if action == 'approve':
                store = application.move_to_store()
                application.status = 'approved'
                application.save()
                return Response(ApplicationSerializer(application).data, status=status.HTTP_200_OK)

            elif action == 'reject':
                application.status = 'rejected'
                application.save()
                return Response({"detail": "Заявка отклонена."}, status=status.HTTP_200_OK)

            else:
                return Response({"detail": "Неверное действие."}, status=status.HTTP_400_BAD_REQUEST)

        except Application.DoesNotExist:
            return Response({"detail": "Заявка не найдена."}, status=status.HTTP_404_NOT_FOUND)