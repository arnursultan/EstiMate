from django.contrib import admin
from .models import ChatRoom, Message

@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "admin", "created_at")
    search_fields = ("user__first_name", "admin__first_name")
    list_filter = ("created_at",)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "chat", "sender", "content", "created_at", "is_read")
    search_fields = ("sender__first_name", "chat__user__first_name", "chat__admin__first_name")
    list_filter = ("created_at", "is_read")
    ordering = ("-created_at",)
