from rest_framework import serializers
from .models import ChatRoom, Message
from users.serializers import UserSerializer

class ChatRoomSerializer(serializers.ModelSerializer):
    participants = UserSerializer(many=True, read_only=True)
    
    class Meta:
        model = ChatRoom
        fields = ['id', 'name', 'participants', 'created_at', 'updated_at']

class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    
    class Meta:
        model = Message
        fields = ['id', 'chat_room', 'sender', 'content', 'created_at', 'is_read']
        read_only_fields = ['chat_room', 'sender'] 