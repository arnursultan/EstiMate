from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    # Эндпоинты для работы с чатами
    path('chats/', views.ChatListView.as_view(), name='chat-list'),
    path('admin/chats/', views.AdminChatListView.as_view(), name='admin-chat-list'),
    path('chats/create/', views.ChatCreateView.as_view(), name='chat-create'),
    path('chats/<int:pk>/', views.ChatDetailView.as_view(), name='chat-detail'),

    # Эндпоинты для работы с сообщениями
    path('chats/<int:chat_id>/messages/', views.MessageListView.as_view(), name='message-list'),
    path('chats/<int:chat_id>/messages/create/', views.MessageCreateView.as_view(), name='message-create'),
    path('chats/<int:chat_id>/mark-read/', views.MarkMessagesAsReadView.as_view(), name='mark-messages-read'),

    # Эндпоинт для получения количества непрочитанных сообщений
    path('unread/', views.UnreadMessagesCountView.as_view(), name='unread-count'),
]