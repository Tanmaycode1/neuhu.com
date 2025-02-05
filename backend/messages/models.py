from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid

class ChatRoom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='chat_rooms')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'chat_chatroom'
        ordering = ['-updated_at']

    def __str__(self):
        participants = self.participants.all()
        if participants.exists():
            return f"Chat between {', '.join(str(p) for p in participants)}"
        return f"Empty Chat Room {self.id}"

class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    attachment = models.FileField(upload_to='chat_attachments/', null=True, blank=True)
    attachment_type = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table = 'chat_message'
        ordering = ['created_at']

    def __str__(self):
        return f"Message from {self.sender} in {self.room}"

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()