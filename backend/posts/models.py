from django.db import models
import uuid
from django.core.files.storage import default_storage
from django.contrib.auth.models import User
from django.conf import settings

class Post(models.Model):
    POST_TYPES = (
        ('NEWS', 'News'),
        ('AUDIO', 'Audio'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    type = models.CharField(max_length=5, choices=POST_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    image = models.ImageField(
        upload_to='posts/images/',
        storage=default_storage,
        null=True,
        blank=True
    )
    audio_file = models.FileField(
        upload_to='audio/',
        storage=default_storage,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    likes = models.ManyToManyField(
        'users.User',
        related_name='liked_posts',
        blank=True
    )
    
    class Meta:
        ordering = ['-created_at']

    def clean(self):
        from django.core.exceptions import ValidationError
        
        if self.type == 'AUDIO' and not self.image:
            raise ValidationError('Image is required for audio posts')  

class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey('users.User', on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class PostInteraction(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post = models.ForeignKey('Post', on_delete=models.CASCADE)
    interaction_type = models.CharField(
        max_length=10,
        choices=[
            ('LIKE', 'Like'),
            ('SHARE', 'Share'),
            ('SAVE', 'Save')
        ]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post', 'interaction_type')

class TrendingScore(models.Model):
    post = models.OneToOneField(Post, on_delete=models.CASCADE, related_name='trending_score')
    score = models.FloatField(default=0)
    view_count = models.IntegerField(default=0)
    like_count = models.IntegerField(default=0)
    comment_count = models.IntegerField(default=0)
    share_count = models.IntegerField(default=0)
    last_calculated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-score']

class PostView(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='views')
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'user')
