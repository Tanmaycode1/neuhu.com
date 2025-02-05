# chat/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import ChatRoom, Message

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'avatar_url']

    def get_avatar_url(self, obj):
        if obj.avatar:
            return obj.avatar.url
        return None

class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    
    class Meta:
        model = Message
        fields = ['id', 'content', 'sender', 'created_at', 'is_read', 'read_at', 
                 'attachment', 'attachment_type']
        read_only_fields = ['sender', 'is_read', 'read_at']

class ChatRoomSerializer(serializers.ModelSerializer):
    participants = UserSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    other_participant = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = ['id', 'participants', 'created_at', 'updated_at', 
                 'last_message', 'unread_count', 'other_participant']

    def get_last_message(self, obj):
        message = obj.get_last_message()
        if message:
            return MessageSerializer(message).data
        return None

    def get_unread_count(self, obj):
        user = self.context['request'].user
        return obj.get_unread_count(user)

    def get_other_participant(self, obj):
        user = self.context['request'].user
        other_participant = obj.participants.exclude(id=user.id).first()
        if other_participant:
            return UserSerializer(other_participant).data
        return None