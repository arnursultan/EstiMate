from django.contrib import admin
from django.utils.html import format_html
from .models import Chat, Message


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ('id', 'admin_display', 'partner_display', 'messages_count', 'created_at', 'updated_at')
    list_filter = ('admin', 'partner', 'created_at')
    search_fields = ('admin__email', 'admin__first_name', 'admin__last_name',
                     'partner__email', 'partner__first_name', 'partner__last_name')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')

    def messages_count(self, obj):
        return obj.messages.count()

    messages_count.short_description = 'Сообщений'

    def admin_display(self, obj):
        return f"{obj.admin.first_name} {obj.admin.last_name} ({obj.admin.email})"

    admin_display.short_description = 'Администратор'

    def partner_display(self, obj):
        return f"{obj.partner.first_name} {obj.partner.last_name} ({obj.partner.email})"

    partner_display.short_description = 'Партнер'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'chat_display', 'sender_display', 'message_type',
                    'short_content', 'file_display', 'timestamp', 'is_read')
    list_filter = ('message_type', 'is_read', 'chat__admin', 'chat__partner', 'timestamp')
    search_fields = ('content', 'sender__email', 'sender__first_name', 'sender__last_name')
    date_hierarchy = 'timestamp'
    readonly_fields = ('timestamp',)
    raw_id_fields = ('chat', 'sender')

    def chat_display(self, obj):
        return f"Чат #{obj.chat.id}: {obj.chat.admin.email} и {obj.chat.partner.email}"

    chat_display.short_description = 'Чат'

    def sender_display(self, obj):
        return f"{obj.sender.first_name} {obj.sender.last_name} ({obj.sender.email})"

    sender_display.short_description = 'Отправитель'

    def short_content(self, obj):
        if not obj.content:
            return "-"
        return obj.content[:50] + ('...' if len(obj.content) > 50 else '')

    short_content.short_description = 'Содержание'

    def file_display(self, obj):
        if obj.file:
            file_url = obj.file.url
            file_name = obj.file.name.split('/')[-1]
            return format_html('<a href="{}" target="_blank">{}</a>', file_url, file_name)
        return '-'

    file_display.short_description = 'Файл'