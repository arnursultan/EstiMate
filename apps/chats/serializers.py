from rest_framework import serializers
from .models import Message

class MessageSerializer(serializers.ModelSerializer):
    sender_email = serializers.EmailField(source='sender.email', read_only=True)
    receiver_email = serializers.EmailField(source='receiver.email', read_only=True)

    type = serializers.ChoiceField(choices=Message.TYPE_CHOICES)  # делаем поле обязательным

    class Meta:
        model = Message
        fields = [
            'id', 'sender', 'sender_email', 'receiver', 'receiver_email',
            'type', 'text', 'file', 'is_read', 'timestamp'
        ]
        read_only_fields = ['sender', 'is_read', 'timestamp']

    def validate(self, data):
        msg_type = data.get('type')
        text = data.get('text')
        file = data.get('file')

        if msg_type == Message.TEXT and not text:
            raise serializers.ValidationError({"text": "Обязательное поле для текстового сообщения."})

        if msg_type in [Message.IMAGE, Message.VIDEO, Message.FILE] and not file:
            raise serializers.ValidationError({"file": "Файл обязателен для данного типа сообщения."})

        return data

    def create(self, validated_data):
        validated_data['sender'] = self.context['request'].user
        return super().create(validated_data)