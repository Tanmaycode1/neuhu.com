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
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
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
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()