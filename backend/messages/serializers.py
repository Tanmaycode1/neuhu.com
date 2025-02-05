from rest_framework import serializers
from .models import ChatRoom, Message
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'avatar_url']
        
    def get_avatar_url(self, obj):
        if hasattr(obj, 'avatar') and obj.avatar:
            return obj.avatar.url
        return None

class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    sender_id = serializers.UUIDField(write_only=True)
    attachment_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'id', 'room', 'sender', 'sender_id', 'content', 
            'created_at', 'is_read', 'read_at',
            'attachment', 'attachment_type', 'attachment_url'
        ]
        read_only_fields = ['is_read', 'read_at']
        
    def get_attachment_url(self, obj):
        if obj.attachment:
            return obj.attachment.url
        return None

class ChatRoomSerializer(serializers.ModelSerializer):
    participants = UserSerializer(many=True, read_only=True)
    last_message = MessageSerializer(read_only=True)
    unread_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = ChatRoom
        fields = [
            'id', 'participants', 'created_at', 
            'updated_at', 'last_message', 'unread_count'
        ]

class ChatRoomListSerializer(ChatRoomSerializer):
    other_participant = serializers.SerializerMethodField()
    
    class Meta(ChatRoomSerializer.Meta):
        fields = ChatRoomSerializer.Meta.fields + ['other_participant']
        
    def get_other_participant(self, obj):
        request = self.context.get('request')
        if request and request.user:
            other_user = obj.participants.exclude(id=request.user.id).first()
            if other_user:
                return UserSerializer(other_user).data
        return None 