from rest_framework import serializers
from .models import User, UserProfile,Notification
from django.conf import settings

class UserProfileSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    follower_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    phone = serializers.CharField(source='profile.phone', required=False, allow_blank=True)
    location = serializers.CharField(source='profile.location', required=False, allow_blank=True)
    birth_date = serializers.DateField(source='profile.birth_date', required=False, allow_null=True)
    website = serializers.URLField(source='profile.website', required=False, allow_blank=True)
    gender = serializers.CharField(source='profile.gender', required=False, allow_blank=True)
    occupation = serializers.CharField(source='profile.occupation', required=False, allow_blank=True)
    company = serializers.CharField(source='profile.company', required=False, allow_blank=True)
    education = serializers.CharField(source='profile.education', required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'username',
            'first_name',
            'last_name',
            'full_name',
            'bio',
            'avatar',
            'avatar_url',
            'social_links',
            'account_privacy',
            'follower_count',
            'following_count',
            'date_joined',
            'last_active',
            'email_verified',
            'is_verified',
            'phone',
            'location',
            'birth_date',
            'website',
            'gender',
            'occupation',
            'company',
            'education'
        ]
        read_only_fields = [
            'id', 
            'email', 
            'date_joined', 
            'last_active', 
            'email_verified',
            'is_verified'
        ]

    def get_avatar_url(self, obj):
        if obj.avatar:
            return obj.avatar.url
        return None

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_follower_count(self, obj):
        return obj.followers.count()

    def get_following_count(self, obj):
        return obj.following.count()

    def update(self, instance, validated_data):
        # Handle profile data
        profile_data = validated_data.pop('profile', {})
        if profile_data:
            profile = instance.profile
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

        # Handle social links
        social_links = validated_data.pop('social_links', None)
        if social_links is not None:
            current_links = instance.social_links or {}
            current_links.update(social_links)
            instance.social_links = current_links

        # Update user fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance

class UserProfileDetailSerializer(UserProfileSerializer):
    """Extended serializer for detailed profile view"""
    profile = serializers.SerializerMethodField()

    class Meta(UserProfileSerializer.Meta):
        fields = UserProfileSerializer.Meta.fields + ['profile']

    def get_profile(self, obj):
        return {
            'phone': obj.profile.phone,
            'location': obj.profile.location,
            'birth_date': obj.profile.birth_date,
            'gender': obj.profile.gender,
            'occupation': obj.profile.occupation,
            'company': obj.profile.company,
            'education': obj.profile.education,
            'language': obj.profile.language,
            'timezone': obj.profile.timezone,
            'post_count': obj.profile.post_count,
            'created_at': obj.profile.created_at,
            'updated_at': obj.profile.updated_at
        }

# Keep existing serializers
class UserSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()
    is_followed = serializers.BooleanField(read_only=True)
    posts_count = serializers.IntegerField(read_only=True)
    followers_count = serializers.IntegerField(read_only=True)
    following_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 
            'email', 'bio', 'avatar', 'is_followed',
            'posts_count', 'followers_count', 'following_count'
        ]

    def get_avatar(self, obj):
        request = self.context.get('request')
        if obj.avatar and hasattr(obj.avatar, 'url'):
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url  # Return relative URL if no request
        return None

class UserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('email', 'password', 'username', 'first_name', 'last_name')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

class UserPublicProfileSerializer(serializers.ModelSerializer):
    follower_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    is_followed = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 'email',
            'avatar_url', 'bio', 'is_followed', 'follower_count',
            'following_count'
        ]
        read_only_fields = fields

    def get_follower_count(self, obj):
        return obj.followers.count()

    def get_following_count(self, obj):
        return obj.following.count()


class NotificationSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'sender', 'message',
            'redirect_url', 'created_at', 'read_at', 'is_read',
            'is_recent'
        ]
