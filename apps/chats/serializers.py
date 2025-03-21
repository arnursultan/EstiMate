from rest_framework import serializers
from .models import ChatRoom, Message
from apps.users.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        ref_name = "ChatUserSerializer"
        model = User
        fields = ["id", "first_name", "last_name", "role"]

class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ["id", "chat", "sender", "content", "created_at", "is_read"]


class ChatRoomSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    admin = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = ChatRoom
        fields = ["id", "user", "admin", "created_at"]


    def get_last_message(self, obj):
        last_msg = obj.messages.last()
        return MessageSerializer(last_msg).data if last_msg else None
