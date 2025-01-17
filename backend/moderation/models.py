from django.db import models
import uuid
from django.contrib.auth import get_user_model

User = get_user_model()

class Report(models.Model):
    REPORT_TYPES = (
        ('SPAM', 'Spam'),
        ('HARASSMENT', 'Harassment'),
        ('INAPPROPRIATE', 'Inappropriate Content'),
        ('VIOLENCE', 'Violence'),
        ('OTHER', 'Other'),
    )

    REPORT_STATUS = (
        ('PENDING', 'Pending Review'),
        ('REVIEWING', 'Under Review'),
        ('RESOLVED', 'Resolved'),
        ('REJECTED', 'Rejected'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_filed')
    reported_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_received')
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    content = models.TextField()
    status = models.CharField(max_length=20, choices=REPORT_STATUS, default='PENDING')
    related_object_type = models.CharField(max_length=50)  # post, comment, message, etc.
    related_object_id = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='resolved_reports'
    )
    resolution_note = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

class ContentFilter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    keyword = models.CharField(max_length=100)
    is_regex = models.BooleanField(default=False)
    replacement = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.keyword
