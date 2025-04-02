from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MessageViewSet, PartnerChatListView

router = DefaultRouter()
router.register(r'messages', MessageViewSet, basename='message')

urlpatterns = [
    path('', include(router.urls)),
    path('partners/', PartnerChatListView.as_view(), name='partner-chat-list'),
]