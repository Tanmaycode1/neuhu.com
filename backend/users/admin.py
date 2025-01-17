from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, UserProfile, EmailVerificationOTP

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'username', 'first_name', 'last_name', 'is_staff', 'email_verified')
    list_filter = ('is_staff', 'is_active', 'email_verified')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('username', 'first_name', 'last_name', 'bio', 'avatar')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'email_verified')}),
        ('Social', {'fields': ('social_links', 'following')}),
        ('Important dates', {'fields': ('last_login', 'last_active')}),  # Removed date_joined as it's non-editable
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2'),
        }),
    )

    readonly_fields = ('last_login', 'last_active')  # These fields are read-only
    inlines = (UserProfileInline,)

    def get_queryset(self, request):
        """Override to handle missing chat tables"""
        qs = super().get_queryset(request)
        try:
            # Try to access chat-related fields only if they exist
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'chat_chatroom_participants'
                    );
                """)
                table_exists = cursor.fetchone()[0]
                
                if not table_exists:
                    # If chat tables don't exist, just return basic user fields
                    qs = qs.only('id', 'email', 'username', 'is_active', 'email_verified', 
                               'last_login', 'is_staff', 'is_superuser')
        except Exception:
            pass
        return qs

    def delete_model(self, request, obj):
        """Override to handle deletion of users"""
        try:
            obj.delete()
        except Exception as e:
            # Log the error but don't prevent deletion
            print(f"Error deleting user: {e}")
            # Try force delete if normal delete fails
            User.objects.filter(id=obj.id).delete()

@admin.register(EmailVerificationOTP)
class EmailVerificationOTPAdmin(admin.ModelAdmin):
    list_display = ('email', 'otp', 'created_at', 'is_used')
    list_filter = ('is_used', 'created_at')
    search_fields = ('email',)
    readonly_fields = ('created_at',)