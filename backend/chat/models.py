from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid

class ChatRoom(models.Model):
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        help_text="Unique identifier for the chat room"
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='chat_rooms',
        help_text="Users participating in this chat room"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the chat room was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the chat room was last updated"
    )

    class Meta:
        db_table = 'chat_chatroom'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['-updated_at']),
            models.Index(fields=['created_at'])
        ]

    def __str__(self):
        participants = self.participants.all()
        if participants.exists():
            return f"Chat between {', '.join(str(p) for p in participants)}"
        return f"Empty Chat Room {self.id}"

    def get_last_message(self):
        """Get the most recent message in the chat room."""
        return self.messages.order_by('-created_at').first()

    def get_unread_count(self, user):
        """Get count of unread messages for a user."""
        return self.messages.filter(
            is_read=False
        ).exclude(
            sender=user
        ).count()

    def mark_messages_as_read(self, user):
        """Mark all messages as read for a user."""
        self.messages.filter(
            is_read=False
        ).exclude(
            sender=user
        ).update(
            is_read=True,
            read_at=timezone.now()
        )

    def delete_all_messages(self, user):
        """Delete all messages in the room for a user."""
        if user in self.participants.all():
            self.messages.all().delete()
            return True
        return False

    def filter_messages(self, **filters):
        """Filter messages based on criteria."""
        messages = self.messages.all()
        
        if 'start_date' in filters:
            messages = messages.filter(created_at__gte=filters['start_date'])
        
        if 'end_date' in filters:
            messages = messages.filter(created_at__lte=filters['end_date'])
        
        if 'is_read' in filters:
            messages = messages.filter(is_read=filters['is_read'])
            
        if 'sender_id' in filters:
            messages = messages.filter(sender_id=filters['sender_id'])
            
        if 'has_attachment' in filters:
            if filters['has_attachment']:
                messages = messages.exclude(attachment='')
            else:
                messages = messages.filter(attachment='')
                
        return messages.order_by('-created_at')

class Message(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the message"
    )
    room = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name='messages',
        help_text="The chat room this message belongs to"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        help_text="User who sent this message"
    )
    content = models.TextField(
        help_text="The message content"
    )
    is_read = models.BooleanField(
        default=False,
        help_text="Whether the message has been read"
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the message was read"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the message was created"
    )
    attachment = models.FileField(
        upload_to='chat_attachments/',
        null=True,
        blank=True,
        help_text="File attached to this message"
    )
    attachment_type = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Type of the attached file"
    )

    class Meta:
        db_table = 'chat_message'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['room', '-created_at']),
            models.Index(fields=['sender', '-created_at']),
            models.Index(fields=['is_read'])
        ]

    def __str__(self):
        return f"Message from {self.sender} in {self.room}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        
        if is_new:
            # Update the chat room's timestamp
            self.room.save(update_fields=['updated_at'])

    def mark_as_read(self):
        """Mark the message as read and update the read timestamp."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])