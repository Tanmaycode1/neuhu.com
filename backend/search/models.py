from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class SearchLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='search_logs')
    query = models.CharField(max_length=255)
    results_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    search_type = models.CharField(
        max_length=20,
        choices=[
            ('ALL', 'All'),
            ('POSTS', 'Posts'),
            ('USERS', 'Users'),
            ('AUDIO', 'Audio')
        ],
        default='ALL'
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['query']),
            models.Index(fields=['created_at']),
            models.Index(fields=['search_type']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.query}"
