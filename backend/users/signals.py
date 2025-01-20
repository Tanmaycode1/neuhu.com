from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, UserProfile
from django.db import transaction

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """Single signal handler to either create or update user profile"""
    with transaction.atomic():
        if created:
            # Only create if it doesn't exist
            UserProfile.objects.get_or_create(
                user=instance,
                defaults={'account_privacy': 'PUBLIC'}
            )
        else:
            # Just update existing profile
            UserProfile.objects.filter(user=instance).update(
                account_privacy=instance.account_privacy
            ) 