from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
import uuid
from django.core.files.storage import default_storage
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
import secrets
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from datetime import timedelta
from django.utils import timezone

# Email Verification OTP Model
class EmailVerificationOTP(models.Model):
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = _('Email Verification OTP')
        verbose_name_plural = _('Email Verification OTPs')

    def is_valid(self):
        # OTP valid for 10 minutes
        return (timezone.now() - self.created_at) < timedelta(minutes=10) and not self.is_used

    @classmethod
    def generate_otp(cls, email):
        # Generate 6 digit OTP
        otp = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
        
        # Delete any existing unused OTPs for this email
        cls.objects.filter(email=email, is_used=False).delete()
        
        # Create new OTP
        verification_otp = cls.objects.create(
            email=email,
            otp=otp
        )
        return otp

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

def user_avatar_path(instance, filename):
    # Generate path like: avatars/user_id/filename
    return f'avatars/{instance.id}/{filename}'

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    first_name = models.CharField(_('first name'), max_length=150, blank=True)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)
    date_joined = models.DateTimeField(_('date joined'), auto_now_add=True)
    is_active = models.BooleanField(_('active'), default=True)
    is_staff = models.BooleanField(_('staff status'), default=False)
    
    bio = models.TextField(max_length=500, blank=True)
    avatar = models.ImageField(
        upload_to=user_avatar_path,
        storage=default_storage,
        null=True,
        blank=True
    )
    following = models.ManyToManyField(
        'self', 
        symmetrical=False,
        related_name='followers',
        blank=True
    )
    
    social_links = models.JSONField(default=dict, blank=True)
    notification_preferences = models.JSONField(default=dict, blank=True)
    
    account_privacy = models.CharField(
        max_length=10,
        choices=[
            ('PUBLIC', 'Public'),
            ('PRIVATE', 'Private')
        ],
        default='PUBLIC'
    )
    
    # Verification fields
    email_verified = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    
    last_login = models.DateTimeField(_('last login'), null=True, blank=True)
    last_active = models.DateTimeField(null=True, blank=True)
    
    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    objects = CustomUserManager()

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-date_joined']
        swappable = 'AUTH_USER_MODEL'
    
    def __str__(self):
        return self.email
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    def create_like_notification(self, liker, post):
     """Create notification when someone likes user's post"""
     from django.contrib.contenttypes.models import ContentType
     from .models import Notification  # Import here to avoid circular import

     return Notification.objects.create(
        recipient=self,
        sender=liker,
        notification_type='LIKE',
        message=f"{liker.username} liked your post",
        redirect_url=f"/posts/{post.id}",
        content_type=ContentType.objects.get_for_model(post.__class__),
        object_id=str(post.id),
        extra_data={
            'post_id': str(post.id),
            'preview': post.content[:100] if hasattr(post, 'content') else ''
        }
     )

    def create_comment_notification(self, commenter, post, comment):
     """Create notification when someone comments on user's post"""
     from django.contrib.contenttypes.models import ContentType
     from .models import Notification

     return Notification.objects.create(
        recipient=self,
        sender=commenter,
        notification_type='COMMENT',
        message=f"{commenter.username} commented on your post",
        redirect_url=f"/posts/{post.id}#comment-{comment.id}",
        content_type=ContentType.objects.get_for_model(post.__class__),
        object_id=str(post.id),
        extra_data={
            'post_id': str(post.id),
            'comment_id': str(comment.id),
            'comment_preview': comment.content[:100] if hasattr(comment, 'content') else ''
        }
     )
        
    def get_unread_notifications_count(self):
        return self.notifications.filter(is_read=False).count()

    def get_recent_notifications(self, limit=10):
        return self.notifications.all()[:limit]

    def mark_all_notifications_as_read(self):
        from django.utils import timezone
        self.notifications.filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )

    def create_follow_notification(self, follower):
        """Create notification when someone follows the user"""
        Notification.objects.create(
            recipient=self,
            sender=follower,
            notification_type='FOLLOW',
            message=f"{follower.username} started following you",
            redirect_url=f"/profile/{follower.id}"
        ) 


    def generate_and_send_otp(self):
     """Generate and send OTP for email verification"""
     otp = EmailVerificationOTP.generate_otp(self.email)
    
     try:
        # Create simple email message directly
        subject = 'Your Email Verification Code'
        message = f"""
        Hi {self.username},

        Your verification code is: {otp}

        This code will expire in 10 minutes.

        If you didn't request this code, please ignore this email.

        Best regards,
        Your App Team
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[self.email],
            fail_silently=False,
        )
        return True
     except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False


    def verify_email_with_otp(self, otp):
        """Verify email with provided OTP"""
        try:
            verification = EmailVerificationOTP.objects.get(
                email=self.email,
                otp=otp,
                is_used=False
            )
            
            if verification.is_valid():
                self.email_verified = True
                self.save()
                
                # Mark OTP as used
                verification.is_used = True
                verification.save()
                
                return True
            return False
        except EmailVerificationOTP.DoesNotExist:
            return False

    def delete(self, *args, **kwargs):
        # Remove related chat relationships before deleting
        try:
            # Only attempt to delete chat relationships if the table exists
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'chat_chatroom_participants'
                    );
                """)
                table_exists = cursor.fetchone()[0]
                
                if table_exists:
                    cursor.execute("""
                        DELETE FROM chat_chatroom_participants 
                        WHERE user_id = %s;
                    """, [str(self.id)])
        except Exception:
            # If there's any error (table doesn't exist, etc.), just pass
            pass
            
        # Continue with normal delete
        super().delete(*args, **kwargs)

class UserProfile(models.Model):
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='profile',
        unique=True  # Explicitly set unique
    )
    
    phone = models.CharField(max_length=15, blank=True)
    location = models.CharField(max_length=100, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    website = models.URLField(max_length=200, blank=True)
    gender = models.CharField(
        max_length=20,
        choices=[
            ('MALE', 'Male'),
            ('FEMALE', 'Female'),
            ('OTHER', 'Other'),
            ('PREFER_NOT_TO_SAY', 'Prefer not to say')
        ],
        blank=True
    )
    
    occupation = models.CharField(max_length=100, blank=True)
    company = models.CharField(max_length=100, blank=True)
    education = models.CharField(max_length=200, blank=True)
    
    language = models.CharField(max_length=10, default='en')
    timezone = models.CharField(max_length=50, default='UTC')
    
    post_count = models.IntegerField(default=0)
    follower_count = models.IntegerField(default=0)
    following_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    account_privacy = models.CharField(
        max_length=10,
        choices=[('PUBLIC', 'Public'), ('PRIVATE', 'Private')],
        default='PUBLIC'
    )

    class Meta:
        verbose_name = _('user profile')
        verbose_name_plural = _('user profiles')

    def __str__(self):
        return f"{self.user.username}'s profile"

    def update_counts(self):
        self.post_count = self.user.posts.count()
        self.follower_count = self.user.followers.count()
        self.following_count = self.user.following.count()
        self.save()

# Signals
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(
            user=instance,
            account_privacy='PUBLIC'
        )

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()


from django.utils.translation import gettext_lazy as _

class Notification(models.Model):
    # Notification Types
    NOTIFICATION_TYPES = [
        ('LIKE', 'Like'),
        ('COMMENT', 'Comment'),
        ('FOLLOW', 'Follow'),
        ('MENTION', 'Mention'),
        ('REPLY', 'Reply'),
        ('SHARE', 'Share')
    ]

    recipient = models.ForeignKey(
        'User', 
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    sender = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_notifications'
    )

    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES
    )

    # Generic foreign key for different content types
    content_type = models.ForeignKey(
        'contenttypes.ContentType',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.CharField(max_length=255, null=True, blank=True)
    
    # Message to display
    message = models.TextField()
    
    # Link to redirect when clicked
    redirect_url = models.CharField(max_length=500, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    
    # Additional metadata
    extra_data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        verbose_name = _('notification')
        verbose_name_plural = _('notifications')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['is_read', '-created_at']),
        ]

    def __str__(self):
        return f"Notification for {self.recipient.username} - {self.notification_type}"

    def mark_as_read(self):
        from django.utils import timezone
        self.is_read = True
        self.read_at = timezone.now()
        self.save()

    @property
    def is_recent(self):
        """Check if notification is less than 24 hours old"""
        from django.utils import timezone
        from datetime import timedelta
        return (timezone.now() - self.created_at) < timedelta(days=1)
