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
        fields = ['id', 'content', 'sender', 'created_at', 'is_read', 'read_at', 'updated_at']
        read_only_fields = ['id', 'sender', 'created_at', 'is_read', 'read_at', 'updated_at']

    def validate_content(self, value):
        """Validate message content."""
        if not value or not value.strip():
            raise serializers.ValidationError("Message content cannot be empty.")
        return value.strip()

    def create(self, validated_data):
        """Create a new message."""
        validated_data['sender'] = self.context['request'].user
        return super().create(validated_data)

    def to_representation(self, instance):
        """Convert message instance to JSON."""
        data = super().to_representation(instance)
        # Ensure sender data is properly formatted
        if instance.sender:
            data['sender'] = UserSerializer(instance.sender).data
        return data

class ChatRoomSerializer(serializers.ModelSerializer):
    participants = UserSerializer(many=True, read_only=True)
    online_participants = UserSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    other_participant = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = ['id', 'participants', 'online_participants', 'created_at', 
                 'updated_at', 'last_message', 'unread_count', 'other_participant']

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