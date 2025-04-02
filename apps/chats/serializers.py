from rest_framework import serializers
from .models import Message


class MessageSerializer(serializers.ModelSerializer):
    sender_email = serializers.EmailField(source='sender.email', read_only=True)
    sender_name = serializers.SerializerMethodField(read_only=True)
    receiver_email = serializers.EmailField(source='receiver.email', read_only=True)
    receiver_name = serializers.SerializerMethodField(read_only=True)
    file_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Message
        fields = [
            'id', 'sender', 'sender_email', 'sender_name', 'receiver', 'receiver_email', 'receiver_name',
            'type', 'text', 'file', 'file_url', 'is_read', 'timestamp'
        ]
        read_only_fields = ['sender', 'is_read', 'timestamp']

    def get_sender_name(self, obj):
        """Получить имя отправителя"""
        if obj.sender:
            return f"{obj.sender.first_name} {obj.sender.last_name}"
        return None

    def get_receiver_name(self, obj):
        """Получить имя получателя"""
        if obj.receiver:
            return f"{obj.receiver.first_name} {obj.receiver.last_name}"
        return None

    def get_file_url(self, obj):
        """Получить URL файла"""
        if obj.file:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.file.url)
        return None

    def validate(self, data):
        """Валидация данных сообщения"""
        msg_type = data.get('type')
        text = data.get('text')
        file = data.get('file')

        if msg_type == Message.TEXT and not text:
            raise serializers.ValidationError({"text": "Обязательное поле для текстового сообщения."})

        if msg_type in [Message.IMAGE, Message.VIDEO, Message.FILE] and not file:
            raise serializers.ValidationError({"file": "Файл обязателен для данного типа сообщения."})

        # Проверка, что партнер может отправлять сообщения только админам
        user = self.context['request'].user
        receiver = data.get('receiver')

        if not user.is_staff and receiver and not receiver.is_staff:
            raise serializers.ValidationError(
                {"receiver": "Партнеры могут отправлять сообщения только администраторам"})

        return data

    def create(self, validated_data):
        """Создание сообщения"""
        validated_data['sender'] = self.context['request'].user
        return super().create(validated_data)