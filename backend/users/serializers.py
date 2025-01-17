from rest_framework import serializers
from .models import User, UserProfile

class UserProfileSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    follower_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()

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
            'is_verified'
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
    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'first_name', 'last_name', 'bio', 'avatar')
        read_only_fields = ('id', 'email')

class UserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('email', 'password', 'username', 'first_name', 'last_name')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user