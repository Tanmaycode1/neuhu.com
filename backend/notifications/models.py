from django.db import models
import uuid
from django.contrib.auth import get_user_model

User = get_user_model()

class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('FOLLOW', 'Follow'),
        ('LIKE', 'Like'),
        ('COMMENT', 'Comment'),
        ('MESSAGE', 'Message'),
        ('MENTION', 'Mention'),
        ('GROUP_INVITE', 'Group Invite'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    content = models.TextField()
    related_object_id = models.UUIDField(null=True, blank=True)  # ID of related post/comment/etc
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.sender.username} -> {self.recipient.username}: {self.notification_type}"
