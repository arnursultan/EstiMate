from rest_framework import serializers
from .models import Chat, Message
from django.contrib.auth import get_user_model

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор для пользователей в контексте чата."""
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role', 'photo', 'full_name']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()


class MessageSerializer(serializers.ModelSerializer):
    """Сериализатор для сообщений чата."""
    sender = UserSerializer(read_only=True)
    file_url = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id',
            'sender',
            'content',
            'file',
            'file_url',
            'file_name',
            'file_size',
            'message_type',
            'timestamp',
            'is_read'
        ]
        extra_kwargs = {
            'file': {'write_only': True, 'required': False},
        }

    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    def get_file_name(self, obj):
        if obj.file:
            return obj.file.name.split('/')[-1]
        return None

    def get_file_size(self, obj):
        if obj.file:
            return obj.file.size
        return None


class ChatSerializer(serializers.ModelSerializer):
    """Сериализатор для отображения информации о чате."""
    admin = UserSerializer(read_only=True)
    partner = UserSerializer(read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Chat
        fields = [
            'id',
            'admin',
            'partner',
            'created_at',
            'updated_at',
            'last_message',
            'unread_count'
        ]

    def get_last_message(self, obj):
        last_message = obj.messages.order_by('-timestamp').first()
        if last_message:
            return MessageSerializer(
                last_message,
                context=self.context
            ).data
        return None

    def get_unread_count(self, obj):
        user = self.context.get('request').user
        return obj.messages.filter(is_read=False).exclude(sender=user).count()


class ChatCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания нового чата."""
    partner_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Chat
        fields = ['partner_id']

    def validate_partner_id(self, value):
        try:
            partner = User.objects.get(id=value, role='partner')
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("Партнер не найден")

    def create(self, validated_data):
        partner_id = validated_data.pop('partner_id')
        partner = User.objects.get(id=partner_id)
        user = self.context['request'].user

        # Только администраторы могут создавать чаты
        if user.role != 'admin':
            raise serializers.ValidationError("Только администраторы могут создавать чаты")

        # Проверка на существующий чат
        existing_chat = Chat.objects.filter(admin=user, partner=partner).first()
        if existing_chat:
            return existing_chat

        # Создание нового чата
        return Chat.objects.create(admin=user, partner=partner)


class MessageCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания новых сообщений."""
    file = serializers.FileField(required=False)

    class Meta:
        model = Message
        fields = ['content', 'file', 'message_type']
        extra_kwargs = {
            'message_type': {'required': True},
        }

    def validate(self, attrs):
        # Проверка наличия контента для текстовых сообщений
        if attrs.get('message_type') == 'text' and not attrs.get('content'):
            raise serializers.ValidationError("Текстовое сообщение не может быть пустым")

        # Проверка наличия файла для сообщений с файлами
        if attrs.get('message_type') in ['image', 'video', 'document'] and not attrs.get('file'):
            raise serializers.ValidationError(f"Сообщение типа {attrs.get('message_type')} должно содержать файл")

        return attrs

    def create(self, validated_data):
        chat_id = self.context['chat_id']
        user = self.context['request'].user

        try:
            chat = Chat.objects.get(id=chat_id)
        except Chat.DoesNotExist:
            raise serializers.ValidationError("Чат не найден")

        # Проверка доступа пользователя к чату
        if user.role == 'admin' and chat.admin != user:
            raise serializers.ValidationError("У вас нет доступа к этому чату")
        elif user.role == 'partner' and chat.partner != user:
            raise serializers.ValidationError("У вас нет доступа к этому чату")

        # Создание сообщения
        message = Message.objects.create(
            chat=chat,
            sender=user,
            **validated_data
        )

        # Обновляем время последнего обновления чата
        chat.save()  # Это триггерит auto_now для updated_at

        return message