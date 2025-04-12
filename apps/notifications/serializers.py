# apps/notifications/serializers.py
from rest_framework import serializers
from .models import Notification, NotificationSettings


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'notification_type', 'title', 'message', 'is_read', 'created_at', 'extra_data']
        read_only_fields = ['id', 'notification_type', 'title', 'message', 'created_at', 'extra_data']


class NotificationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationSettings
        fields = ['order_status_notifications', 'store_approval_notifications',
                 'registration_notifications', 'message_notifications',
                 'financial_notifications', 'system_notifications']