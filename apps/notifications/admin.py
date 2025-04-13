# apps/notifications/admin.py
from django.contrib import admin
from .models import Notification, NotificationSettings


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notification_type', 'title', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at', 'user__role')
    search_fields = ('title', 'message', 'user__email', 'user__first_name', 'user__last_name')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'order_status_notifications', 'message_notifications',
                   'financial_notifications', 'system_notifications', 'store_approval_notifications',
                   'registration_notifications')
    list_filter = ('order_status_notifications', 'message_notifications',
                   'financial_notifications', 'system_notifications', 'user__role')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')