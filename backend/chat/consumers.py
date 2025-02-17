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
from django.db import transaction
import traceback
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from collections import defaultdict
from .connection import connection_manager

logger = logging.getLogger(__name__)
User = get_user_model()

@dataclass
class RateLimiter:
    """Rate limiter using token bucket algorithm."""
    rate: float  # tokens per second
    capacity: float  # bucket size
    tokens: float = 0.0
    last_update: float = 0.0

    def update(self) -> None:
        now = time.time()
        time_passed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + time_passed * self.rate)
        self.last_update = now

    def try_acquire(self, tokens: float = 1.0) -> bool:
        self.update()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

class ConnectionManager:
    """Manages active WebSocket connections."""
    def __init__(self):
        self._connections: Dict[str, 'ChatConsumer'] = {}
        self._user_rate_limiters: Dict[str, Dict[str, RateLimiter]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    def get_rate_limiter(self, user_id: str, room_id: str, limiter_type: str) -> RateLimiter:
        """Get or create a rate limiter for a user in a room."""
        if limiter_type not in self._user_rate_limiters[user_id]:
            if limiter_type == 'message':
                # 10 messages per second, burst of 20
                self._user_rate_limiters[user_id][limiter_type] = RateLimiter(10, 20)
            elif limiter_type == 'connection':
                # 2 connections per second, burst of 5
                self._user_rate_limiters[user_id][limiter_type] = RateLimiter(2, 5)
        return self._user_rate_limiters[user_id][limiter_type]

    async def register(self, connection_key: str, consumer: 'ChatConsumer') -> Optional['ChatConsumer']:
        """Register a new connection, returns existing connection if any."""
        async with self._lock:
            existing = self._connections.get(connection_key)
            self._connections[connection_key] = consumer
            return existing

    async def unregister(self, connection_key: str, consumer: 'ChatConsumer') -> None:
        """Unregister a connection."""
        async with self._lock:
            if self._connections.get(connection_key) == consumer:
                self._connections.pop(connection_key, None)

    def get_connection(self, connection_key: str) -> Optional['ChatConsumer']:
        """Get an existing connection."""
        return self._connections.get(connection_key)

# Global connection manager
connection_manager = ConnectionManager()

class ChatConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.room_id = None
        self.room_group_name = None
        self._is_connected = False
        self._connection_id = None
        self._ping_task = None
        self._cleanup_lock = asyncio.Lock()
        self._message_queue = asyncio.Queue(maxsize=100)
        self._last_activity = time.time()
        self._close_code = None
        self._close_reason = None
        self._message_processor_task = None
        self._health_check_task = None
        self._error_count = 0
        self._max_errors = 3
        self._last_error_time = 0
        self._error_window = 60  # 1 minute window for error counting

    @classmethod
    def get_connection_key(cls, user_id, room_id):
        return f"{user_id}_{room_id}"

    async def connect(self):
        try:
            if self.scope['user'].is_anonymous:
                logger.error("Anonymous user tried to connect")
                await self.close(code=4001)
                return

            self.user = self.scope['user']
            self.room_id = self.scope['url_route']['kwargs']['room_id']
            self.room_group_name = f'chat_{self.room_id}'
            self._connection_id = f"{self.user.id}_{self.room_id}_{id(self)}"

            # Check if user can connect
            if not await connection_manager.can_add_connection(str(self.user.id), self.room_id):
                logger.warning(f"Connection limit reached for user {self.user.id} in room {self.room_id}")
                await self.close(code=4029)
                return

            logger.info(f"Connection attempt from user {self.user.id} to room {self.room_id}")

            # Verify room exists and user is participant
            if not await self.verify_participant():
                logger.error(f"User {self.user.id} is not a participant in room {self.room_id}")
                await self.close(code=4002)
                return

            # Register connection with manager
            metadata = {
                'username': self.user.username,
                'room_name': self.room_group_name,
                'client_ip': self.scope.get('client', ['0.0.0.0'])[0],
                'user_agent': self.scope.get('headers', {}).get('user-agent', b'').decode(),
            }
            
            if not await connection_manager.add_connection(
                str(self.user.id),
                self.room_id,
                self._connection_id,
                metadata
            ):
                logger.error(f"Failed to register connection for user {self.user.id}")
                await self.close(code=4500)
                return

            # Accept the connection
            await self.accept()
            self._is_connected = True
            
            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )

            # Mark user as online and notify others
            if await self.update_user_status(True):
                await self.notify_user_status('online')
                logger.info(f"User {self.user.id} marked as online in room {self.room_id}")

            # Send last few messages
            await self.send_chat_history()

            # Start tasks
            self._ping_task = asyncio.create_task(self._ping_loop())
            self._message_processor_task = asyncio.create_task(self._process_message_queue())
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            
            logger.info(f"User {self.user.id} connected to room {self.room_id}")

        except Exception as e:
            logger.error(f"Connection error: {str(e)}", exc_info=True)
            await self.force_disconnect()
            raise StopConsumer()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnect."""
        try:
            self._close_code = close_code
            await self.force_disconnect()
        except Exception as e:
            logger.error(f"Disconnect error: {str(e)}", exc_info=True)
        finally:
            raise StopConsumer()

    async def force_disconnect(self):
        """Force disconnect and cleanup resources."""
        async with self._cleanup_lock:
            try:
                # Cancel all tasks
                for task in [self._ping_task, self._message_processor_task, self._health_check_task]:
                    if task and not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass

                if self._is_connected:
                    # Remove from connection manager
                    if self._connection_id:
                        await connection_manager.remove_connection(self._connection_id)

                    # Update online status
                    await self.update_user_status(False)
                    await self.notify_user_status('offline')

                    # Leave room group
                    if self.room_group_name and self.channel_name:
                        await self.channel_layer.group_discard(
                            self.room_group_name,
                            self.channel_name
                        )

                    self._is_connected = False
                    
                    # Close WebSocket connection if not already closed
                    if not self._close_code:
                        await self.close()

                logger.info(f"User {self.user.id if self.user else 'Unknown'} disconnected from room {self.room_id if self.room_id else 'Unknown'}")

            except Exception as e:
                logger.error(f"Force disconnect error: {str(e)}", exc_info=True)

    async def _health_check_loop(self):
        """Periodic health check of the connection."""
        while True:
            try:
                if not self._is_connected:
                    break

                # Check error threshold
                current_time = time.time()
                if current_time - self._last_error_time > self._error_window:
                    self._error_count = 0  # Reset error count after window

                # Perform health checks
                is_healthy = await self._perform_health_check()
                
                if not is_healthy:
                    self._error_count += 1
                    self._last_error_time = current_time
                    
                    if self._error_count >= self._max_errors:
                        logger.error(f"Health check failed {self._error_count} times, disconnecting")
                        await self.force_disconnect()
                        break

                await asyncio.sleep(60)  # Check every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {str(e)}")
                await asyncio.sleep(5)  # Short delay on error

    async def _perform_health_check(self) -> bool:
        """Perform various health checks."""
        try:
            # Check database connection
            if not await self._check_database():
                logger.error("Database health check failed")
                return False

            # Check channel layer
            if not await self._check_channel_layer():
                logger.error("Channel layer health check failed")
                return False

            # Check connection manager
            if not await self._check_connection_manager():
                logger.error("Connection manager health check failed")
                return False

            # Check message queue health
            if self._message_queue.qsize() >= self._message_queue.maxsize * 0.9:
                logger.warning("Message queue near capacity")
                return False

            return True
        except Exception as e:
            logger.error(f"Health check error: {str(e)}")
            return False

    @database_sync_to_async
    def _check_database(self) -> bool:
        """Check database connection."""
        try:
            # Quick query to verify database connection
            ChatRoom.objects.filter(id=self.room_id).exists()
            return True
        except Exception as e:
            logger.error(f"Database check failed: {str(e)}")
            return False

    async def _check_channel_layer(self) -> bool:
        """Check channel layer health."""
        try:
            # Try to send a test message to ourselves
            test_channel = f"healthcheck.{self._connection_id}"
            await self.channel_layer.group_add(test_channel, self.channel_name)
            await self.channel_layer.group_discard(test_channel, self.channel_name)
            return True
        except Exception as e:
            logger.error(f"Channel layer check failed: {str(e)}")
            return False

    async def _check_connection_manager(self) -> bool:
        """Check connection manager health."""
        try:
            # Verify our connection is still registered
            if not await connection_manager.get_connection_info(self._connection_id):
                logger.error("Connection not found in manager")
                return False
            return True
        except Exception as e:
            logger.error(f"Connection manager check failed: {str(e)}")
            return False

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            if not self._is_connected:
                return

            # Update last activity
            self._last_activity = time.time()
            await connection_manager.update_activity(self._connection_id)
            
            # Reset error count on successful message
            if time.time() - self._last_error_time > self._error_window:
                self._error_count = 0
            
            # Parse message
            try:
                data = json.loads(text_data)
            except json.JSONDecodeError:
                logger.error("Invalid JSON received")
                self._error_count += 1
                self._last_error_time = time.time()
                return

            message_type = data.get('type')
            
            if message_type == 'chat_message':
                # Queue message for processing
                try:
                    await self._message_queue.put({
                        'type': 'chat_message',
                        'content': data.get('content', '').strip()
                    })
                except asyncio.QueueFull:
                    logger.error("Message queue full")
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'Too many pending messages'
                    }))
                    self._error_count += 1
                    self._last_error_time = time.time()

            elif message_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
            elif message_type == 'health_check':
                is_healthy = await self._perform_health_check()
                await self.send(text_data=json.dumps({
                    'type': 'health_check_response',
                    'healthy': is_healthy
                }))

        except Exception as e:
            logger.error(f"Receive error: {str(e)}", exc_info=True)
            self._error_count += 1
            self._last_error_time = time.time()
            if not self._is_connected:
                await self.close(code=4003)

    async def _process_message_queue(self):
        """Process messages from the queue."""
        while True:
            try:
                message = await self._message_queue.get()
                
                if message['type'] == 'chat_message':
                    content = message['content']
                    if not content:
                        continue

                    # Save and broadcast message
                    saved_message = await self.save_message(content)
                    if saved_message:
                        await self.channel_layer.group_send(
                            self.room_group_name,
                            {
                                'type': 'chat_message',
                                'message': await self.format_message(saved_message)
                            }
                        )
                        logger.info(f"Message sent in room {self.room_id} by user {self.user.id}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                continue
            finally:
                self._message_queue.task_done()

    async def _ping_loop(self):
        """Send periodic pings to keep connection alive."""
        try:
            while True:
                if self._is_connected:
                    current_time = time.time()
                    # Check for inactivity
                    if current_time - self._last_activity > 300:  # 5 minutes
                        logger.warning(f"Connection inactive for user {self.user.id} in room {self.room_id}")
                        await self.force_disconnect()
                        break

                    try:
                        await self.send(text_data=json.dumps({'type': 'ping'}))
                        # Update activity in connection manager
                        await connection_manager.update_activity(self._connection_id)
                    except Exception:
                        await self.force_disconnect()
                        break

                await asyncio.sleep(30)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Ping loop error: {str(e)}")
            await self.force_disconnect()

    @database_sync_to_async
    def verify_participant(self) -> bool:
        """Verify if user is a participant in the room."""
        try:
            with transaction.atomic(timeout=3):  # 3 second timeout
                room = ChatRoom.objects.select_for_update(nowait=True).get(id=self.room_id)
                return room.participants.filter(id=self.user.id).exists()
        except ObjectDoesNotExist:
            logger.error(f"Room {self.room_id} does not exist")
            return False
        except Exception as e:
            logger.error(f"Error verifying participant: {str(e)}")
            return False

    @database_sync_to_async
    def update_user_status(self, is_online: bool) -> bool:
        """Update user's online status in the room."""
        try:
            with transaction.atomic(timeout=3):
                room = ChatRoom.objects.select_for_update(nowait=True).get(id=self.room_id)
                if is_online:
                    if not room.online_participants.filter(id=self.user.id).exists():
                        room.online_participants.add(self.user)
                else:
                    room.online_participants.remove(self.user)
                return True
        except Exception as e:
            logger.error(f"Error updating user status: {str(e)}")
            return False

    @database_sync_to_async
    def save_message(self, content: str) -> Optional[Message]:
        """Save a new message to the database."""
        try:
            with transaction.atomic(timeout=3):
                return Message.objects.create(
                    room_id=self.room_id,
                    sender=self.user,
                    content=content
                )
        except Exception as e:
            logger.error(f"Error saving message: {str(e)}")
            return None

    async def send_chat_history(self):
        """Send recent chat history to the user."""
        try:
            messages = await self.get_last_messages()
            if messages:
                await self.send(text_data=json.dumps({
                    'type': 'chat_history',
                    'messages': messages
                }))
        except Exception as e:
            logger.error(f"Error sending chat history: {str(e)}")

    @database_sync_to_async
    def get_last_messages(self, limit: int = 50) -> list:
        """Get recent messages from the room."""
        try:
            messages = Message.objects.filter(
                room_id=self.room_id
            ).select_related('sender').order_by('-created_at')[:limit]
            
            return [
                {
                    'id': str(msg.id),
                    'content': msg.content,
                    'sender': {
                        'id': str(msg.sender.id),
                        'username': msg.sender.username
                    },
                    'created_at': msg.created_at.isoformat()
                }
                for msg in messages
            ]
        except Exception as e:
            logger.error(f"Error getting last messages: {str(e)}")
            return []

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

    async def format_message(self, message):
        return await sync_to_async(self.format_message_sync)(message)

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