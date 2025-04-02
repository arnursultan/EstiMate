from django.contrib import admin
from .models import Message


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'receiver', 'type', 'text_preview', 'is_read', 'timestamp')
    list_filter = ('is_read', 'type', 'timestamp')
    search_fields = ('sender__email', 'receiver__email', 'text')
    date_hierarchy = 'timestamp'

    def text_preview(self, obj):
        """Предпросмотр текста сообщения"""
        if obj.text:
            return obj.text[:50] + ('...' if len(obj.text) > 50 else '')
        elif obj.file:
            return f"[Файл: {obj.file.name}]"
        return "-"

    text_preview.short_description = "Текст сообщения"

    readonly_fields = ('timestamp',)

    fieldsets = (
        ('Пользователи', {
            'fields': ('sender', 'receiver')
        }),
        ('Сообщение', {
            'fields': ('type', 'text', 'file', 'is_read')
        }),
        ('Метаданные', {
            'fields': ('timestamp',)
        }),
    )

    def has_delete_permission(self, request, obj=None):
        # Запрещаем удаление сообщений для сохранения истории
        if obj and obj.is_read:
            return False
        return True