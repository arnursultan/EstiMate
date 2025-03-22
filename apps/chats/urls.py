from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ChatRoomViewSet, MessageViewSet

router = DefaultRouter()
router.register(r"chats", ChatRoomViewSet, basename="chatroom")  # 👈 Добавляем basename

router.register(r"messages", MessageViewSet)

urlpatterns = [
    path("", include(router.urls)),
]