from django.db import models
import uuid
from django.contrib.auth import get_user_model

User = get_user_model()

class SystemLog(models.Model):
    LOG_LEVELS = (
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    )

    LOG_TYPES = (
        ('AUTH', 'Authentication'),
        ('USER', 'User Action'),
        ('CONTENT', 'Content Moderation'),
        ('SYSTEM', 'System'),
        ('ADMIN', 'Admin Action'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    level = models.CharField(max_length=10, choices=LOG_LEVELS)
    type = models.CharField(max_length=10, choices=LOG_TYPES)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=255)
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['level', 'type']),
            models.Index(fields=['user', 'timestamp']),
        ]

class UserRole(models.Model):
    ROLE_TYPES = (
        ('SUPERUSER', 'Super User'),
        ('ADMIN', 'Administrator'),
        ('MODERATOR', 'Moderator'),
        ('STAFF', 'Staff'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='role')
    role_type = models.CharField(max_length=20, choices=ROLE_TYPES)
    permissions = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='created_roles'
    )

    def __str__(self):
        return f"{self.user.username} - {self.role_type}"

class ModeratorAction(models.Model):
    ACTION_TYPES = (
        ('POST_REMOVE', 'Remove Post'),
        ('POST_RESTORE', 'Restore Post'),
        ('USER_WARN', 'Warn User'),
        ('USER_SUSPEND', 'Suspend User'),
        ('USER_BAN', 'Ban User'),
        ('USER_RESTORE', 'Restore User'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    moderator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mod_actions')
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    target_user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='moderation_records'
    )
    reason = models.TextField()
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True) 