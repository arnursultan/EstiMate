from django.contrib import admin
from .models import Message

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'receiver', 'type', 'is_read', 'timestamp')
    list_filter = ('is_read', 'type', 'timestamp')
    search_fields = ('sender__email', 'receiver__email', 'text')
