from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import ChatRoom, Message
import json
import logging
from channels.exceptions import StopConsumer
import datetime
from asgiref.sync import sync_to_async
from django.core.exceptions import ObjectDoesNotExist
import asyncio

logger = logging.getLogger(__name__)
User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    # Class-level variable to track active connections
    _active_connections = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.room_id = None
        self.room_group_name = None
        self._is_connected = False
        self._connection_id = None
        self._ping_task = None

    @classmethod
    def get_connection_key(cls, user_id, room_id):
        return f"{user_id}_{room_id}"

    async def connect(self):
        try:
            # Get user and room info
            if self.scope['user'].is_anonymous:
                logger.error("Anonymous user tried to connect")
                await self.close(code=4001)
                return

            self.user = self.scope['user']
            self.room_id = self.scope['url_route']['kwargs']['room_id']
            self.room_group_name = f'chat_{self.room_id}'
            self._connection_id = f"{self.user.id}_{self.room_id}_{id(self)}"

            # Check connection limit
            connection_key = self.get_connection_key(self.user.id, self.room_id)
            if connection_key in self._active_connections:
                existing_consumer = self._active_connections[connection_key]
                logger.warning(f"Found existing connection for user {self.user.id} in room {self.room_id}")
                # Force close existing connection
                try:
                    await existing_consumer.force_disconnect()
                except Exception as e:
                    logger.error(f"Error closing existing connection: {str(e)}")
                # Wait for cleanup
                await asyncio.sleep(1)

            # Verify room exists and user is participant
            if not await self.verify_participant():
                logger.error(f"User {self.user.id} is not a participant in room {self.room_id}")
                await self.close(code=4002)
                return

            # Store this connection
            self._active_connections[connection_key] = self

            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )

            # Accept the connection
            await self.accept()
            self._is_connected = True

            # Mark user as online and notify others
            await self.update_user_status(True)
            await self.notify_user_status('online')

            # Send last few messages to the newly connected user
            last_messages = await self.get_last_messages()
            if last_messages:
                await self.send(text_data=json.dumps({
                    'type': 'chat_history',
                    'messages': last_messages
                }))

            # Start ping task
            self._ping_task = asyncio.create_task(self._ping_loop())

            logger.info(f"User {self.user.id} connected to room {self.room_id} with connection ID {self._connection_id}")

        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            await self.force_disconnect()
            raise StopConsumer()

    async def force_disconnect(self):
        """Force disconnect and cleanup this connection."""
        try:
            if self._ping_task:
                self._ping_task.cancel()
                try:
                    await self._ping_task
                except asyncio.CancelledError:
                    pass

            if self._is_connected:
                await self.notify_user_status('offline')
                await self.update_user_status(False)
                
                if hasattr(self, 'room_group_name') and hasattr(self, 'channel_name'):
                    await self.channel_layer.group_discard(
                        self.room_group_name,
                        self.channel_name
                    )

            # Remove from active connections
            connection_key = self.get_connection_key(self.user.id, self.room_id)
            self._active_connections.pop(connection_key, None)
            
            await self.close()
        except Exception as e:
            logger.error(f"Force disconnect error: {str(e)}")

    async def disconnect(self, close_code):
        try:
            await self.force_disconnect()
        except Exception as e:
            logger.error(f"Disconnect error: {str(e)}")
        finally:
            raise StopConsumer()

    async def _ping_loop(self):
        """Send periodic pings to keep connection alive."""
        try:
            while True:
                if self._is_connected:
                    try:
                        await self.send(text_data=json.dumps({'type': 'ping'}))
                    except Exception:
                        # If send fails, force disconnect
                        await self.force_disconnect()
                        break
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Ping loop error: {str(e)}")
            await self.force_disconnect()

    async def notify_user_status(self, status):
        """Send user status update to the group."""
        try:
            if self._is_connected:  # Only send if we're still connected
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'user_status',
                        'user_id': str(self.user.id),
                        'status': status,
                        'timestamp': datetime.datetime.now().isoformat()
                    }
                )
        except Exception as e:
            logger.error(f"Error sending status notification: {str(e)}")

    async def receive(self, text_data):
        try:
            if not self._is_connected:
                return
                
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'chat_message':
                content = data.get('content', '').strip()
                if not content:
                    return
                
                # Save message
                message = await self.save_message(content)
                
                # Broadcast message
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': await self.format_message(message)
                    }
                )
                logger.info(f"Message sent in room {self.room_id} by user {self.user.id}")
            elif message_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
        except Exception as e:
            logger.error(f"Receive error: {str(e)}")
            if not self._is_connected:
                await self.close(code=4003)

    async def chat_message(self, event):
        try:
            if self._is_connected:
                await self.send(text_data=json.dumps(event))
        except Exception as e:
            logger.error(f"Chat message error: {str(e)}")

    async def user_status(self, event):
        try:
            if self._is_connected:
                await self.send(text_data=json.dumps(event))
        except Exception as e:
            logger.error(f"Status message error: {str(e)}")

    @database_sync_to_async
    def verify_participant(self):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            return room.participants.filter(id=self.user.id).exists()
        except ObjectDoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Verify participant error: {str(e)}")
            return False

    @database_sync_to_async
    def update_user_status(self, is_online):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            if is_online:
                return room.add_online_participant(self.user)
            else:
                return room.remove_online_participant(self.user)
        except Exception as e:
            logger.error(f"Error updating user status: {str(e)}")
            return False

    @database_sync_to_async
    def save_message(self, content):
        room = ChatRoom.objects.get(id=self.room_id)
        return Message.objects.create(
            room=room,
            sender=self.user,
            content=content
        )

    @database_sync_to_async
    def get_last_messages(self, limit=50):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            messages = room.messages.select_related('sender').order_by('-created_at')[:limit]
            return [self.format_message_sync(msg) for msg in messages]
        except Exception as e:
            logger.error(f"Error getting last messages: {str(e)}")
            return []

    def format_message_sync(self, message):
        return {
            'id': str(message.id),
            'content': message.content,
            'sender': {
                'id': str(message.sender.id),
                'username': message.sender.username,
                'avatar_url': message.sender.avatar.url if message.sender.avatar else None
            },
            'created_at': message.created_at.isoformat(),
            'is_read': message.is_read,
            'room_id': str(self.room_id)
        }

    async def format_message(self, message):
        return await sync_to_async(self.format_message_sync)(message)