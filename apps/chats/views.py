from rest_framework import viewsets, permissions
from .models import Message
from .serializers import MessageSerializer

class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Проверка на swagger_fake_view
        if getattr(self, 'swagger_fake_view', False):
            return Message.objects.none()

        # Проверка аутентификации пользователя
        user = self.request.user
        if user.is_authenticated:
            return Message.objects.filter(sender=user) | Message.objects.filter(receiver=user)
        else:
            return Message.objects.none()

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)
