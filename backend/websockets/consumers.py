import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from messaging.models import ChatRoom, Message, UserPresence, MessageReaction, Post
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        self.user = self.scope['user']

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        if await self.can_access_room():
            # Set user as online
            await self.set_user_online()
            # Notify others about user's presence
            await self.notify_user_presence(True)
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, close_code):
        # Set user as offline
        await self.set_user_offline()
        # Notify others about user's presence
        await self.notify_user_presence(False)
        
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')

        if message_type == 'message':
            await self.handle_message(data)
        elif message_type == 'typing':
            await self.handle_typing(data)
        elif message_type == 'edit':
            await self.handle_edit(data)
        elif message_type == 'delete':
            await self.handle_delete(data)
        elif message_type == 'reaction':
            await self.handle_reaction(data)

    async def handle_message(self, data):
        message = data.get('message')
        shared_post_id = data.get('shared_post_id')
        
        if shared_post_id:
            # Handle shared post
            try:
                post = await self.get_post(shared_post_id)
                message_content = {
                    'type': 'shared_post',
                    'post_id': str(post.id),
                    'title': post.title,
                    'message': message
                }
                saved_message = await self.save_message(json.dumps(message_content))
            except Post.DoesNotExist:
                return
        else:
            # Handle regular message
            saved_message = await self.save_message(message)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': {
                    'id': str(saved_message.id),
                    'content': saved_message.content,
                    'sender': {
                        'id': str(self.user.id),
                        'username': self.user.username
                    },
                    'created_at': saved_message.created_at.isoformat(),
                    'is_read': False
                }
            }
        )

    async def handle_typing(self, data):
        is_typing = data.get('is_typing', False)
        await self.update_typing_status(is_typing)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_status',
                'user': str(self.user.id),
                'username': self.user.username,
                'is_typing': is_typing
            }
        )

    async def handle_edit(self, data):
        message_id = data.get('message_id')
        new_content = data.get('content')
        
        if await self.update_message(message_id, new_content):
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_edited',
                    'message_id': message_id,
                    'content': new_content,
                    'editor': str(self.user.id)
                }
            )

    async def handle_delete(self, data):
        message_id = data.get('message_id')
        
        if await self.delete_message(message_id):
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_deleted',
                    'message_id': message_id,
                    'user': str(self.user.id)
                }
            )

    async def handle_reaction(self, data):
        message_id = data.get('message_id')
        emoji = data.get('emoji')
        
        reaction = await self.toggle_reaction(message_id, emoji)
        if reaction:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_reaction',
                    'message_id': message_id,
                    'user': str(self.user.id),
                    'emoji': emoji,
                    'action': reaction['action']
                }
            )

    # Message handlers
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'data': event['message']
        }))

    async def typing_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'data': {
                'user': event['user'],
                'username': event['username'],
                'is_typing': event['is_typing']
            }
        }))

    async def message_edited(self, event):
        await self.send(text_data=json.dumps({
            'type': 'edit',
            'data': {
                'message_id': event['message_id'],
                'content': event['content'],
                'editor': event['editor']
            }
        }))

    async def message_deleted(self, event):
        await self.send(text_data=json.dumps({
            'type': 'delete',
            'data': {
                'message_id': event['message_id'],
                'user': event['user']
            }
        }))

    async def message_reaction(self, event):
        await self.send(text_data=json.dumps({
            'type': 'reaction',
            'data': {
                'message_id': event['message_id'],
                'user': event['user'],
                'emoji': event['emoji'],
                'action': event['action']
            }
        }))

    # Database operations
    @database_sync_to_async
    def can_access_room(self):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            return room.participants.filter(id=self.user.id).exists()
        except ChatRoom.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, content, reply_to_id=None):
        room = ChatRoom.objects.get(id=self.room_id)
        reply_to = None
        if reply_to_id:
            try:
                reply_to = Message.objects.get(id=reply_to_id)
            except Message.DoesNotExist:
                pass
        
        message = Message.objects.create(
            room=room,
            sender=self.user,
            content=content,
            reply_to=reply_to
        )
        return message

    @database_sync_to_async
    def update_message(self, message_id, new_content):
        try:
            message = Message.objects.get(id=message_id, sender=self.user)
            message.content = new_content
            message.is_edited = True
            message.save()
            return True
        except Message.DoesNotExist:
            return False

    @database_sync_to_async
    def delete_message(self, message_id):
        try:
            message = Message.objects.get(id=message_id, sender=self.user)
            message.is_deleted = True
            message.content = "This message has been deleted"
            message.save()
            return True
        except Message.DoesNotExist:
            return False

    @database_sync_to_async
    def toggle_reaction(self, message_id, emoji):
        try:
            message = Message.objects.get(id=message_id)
            reaction, created = MessageReaction.objects.get_or_create(
                message=message,
                user=self.user,
                emoji=emoji
            )
            if not created:
                reaction.delete()
                return {'action': 'removed'}
            return {'action': 'added'}
        except Message.DoesNotExist:
            return None

    @database_sync_to_async
    def update_typing_status(self, is_typing):
        room = ChatRoom.objects.get(id=self.room_id)
        if is_typing:
            room.typing_users.add(self.user)
        else:
            room.typing_users.remove(self.user)

    @database_sync_to_async
    def set_user_online(self):
        presence, _ = UserPresence.objects.get_or_create(user=self.user)
        presence.is_online = True
        presence.current_room = ChatRoom.objects.get(id=self.room_id)
        presence.save()

    @database_sync_to_async
    def set_user_offline(self):
        UserPresence.objects.filter(user=self.user).update(
            is_online=False,
            current_room=None,
            last_seen=timezone.now()
        )

    async def notify_user_presence(self, is_online):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_presence',
                'user': str(self.user.id),
                'username': self.user.username,
                'is_online': is_online,
                'timestamp': timezone.now().isoformat()
            }
        ) 

    @database_sync_to_async
    def get_post(self, post_id):
        return Post.objects.get(id=post_id) 