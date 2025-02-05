from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import ChatRoom, Message
import json

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    
    async def connect(self):
        print("Attempting to connect...")  # Debug print
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        self.user = self.scope['user']

        print(f"Room ID: {self.room_id}")  # Debug print
        print(f"User: {self.user}")  # Debug print

        # Verify room exists and user is a participant
        is_participant = await self.verify_participant()
        print(f"Is participant: {is_participant}")  # Debug print

        if not is_participant:
            print("User is not a participant. Closing connection...")  # Debug print
            await self.close()
            return

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        print("Connection accepted")  # Debug print

        # Send user online status
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_status',
                'user_id': str(self.user.id),
                'status': 'online'
            }
        )

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            # Send offline status before leaving
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_status',
                    'user_id': str(self.user.id),
                    'status': 'offline'
                }
            )
            
            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'chat_message':
                content = data.get('content')
                if content:
                    # Save message
                    message = await self.save_message(content)
                    
                    # Send message to room group
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'chat_message',
                            'message': {
                                'id': str(message.id),
                                'content': message.content,
                                'sender': {
                                    'id': str(message.sender.id),
                                    'username': message.sender.username,
                                    'avatar': message.sender.avatar.url if message.sender.avatar else None
                                },
                                'created_at': message.created_at.isoformat(),
                                'is_read': message.is_read
                            }
                        }
                    )
        except json.JSONDecodeError:
            pass

    async def chat_message(self, event):
        message = event['message']
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': message
        }))

    async def user_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_status',
            'user_id': event['user_id'],
            'status': event['status']
        }))

    @database_sync_to_async
    def verify_participant(self):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            return room.participants.filter(id=self.user.id).exists()
        except ChatRoom.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, content):
        room = ChatRoom.objects.get(id=self.room_id)
        return Message.objects.create(
            room=room,
            sender=self.user,
            content=content
        )