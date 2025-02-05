from rest_framework import serializers
from .models import Post, Comment, TrendingScore, PostInteraction
from users.serializers import UserSerializer
from django.conf import settings

class CommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    is_author = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = ('id', 'author', 'content', 'created_at', 'is_author')

    def get_is_author(self, obj):
        """
        Check if the current user is the author of the comment.
        Returns True if the current authenticated user is the author, False otherwise.
        """
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            return obj.author.id == request.user.id  # Compare IDs instead of objects
        return False

class TrendingScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrendingScore
        fields = ('score', 'view_count', 'like_count', 'comment_count', 'share_count')

class PostSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    is_liked = serializers.BooleanField(read_only=True, default=False)
    is_saved = serializers.BooleanField(read_only=True, default=False)
    comments_count = serializers.IntegerField(source='comments.count', read_only=True)
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)
    trending_data = TrendingScoreSerializer(source='trending_score', read_only=True)
    image_url = serializers.SerializerMethodField()
    audio_url = serializers.SerializerMethodField()
    cover_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Post
        fields = [
            'id', 'type', 'title', 'description', 
            'image', 'image_url', 'cover_image_url',
            'audio_file', 'audio_url',
            'author', 'created_at', 'updated_at',
            'comments_count', 'likes_count', 'is_liked', 
            'is_saved', 'trending_data'
        ]
        read_only_fields = (
            'id', 'author', 'image_url', 'audio_url', 'cover_image_url',
            'created_at', 'updated_at', 'comments_count', 'likes_count',
            'is_liked', 'is_saved', 'trending_data'
        )

    def get_image_url(self, obj):
        """Return image URL only for NEWS posts"""
        request = self.context.get('request')
        if obj.type == 'NEWS' and obj.image and hasattr(obj.image, 'url'):
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None

    def get_cover_image_url(self, obj):
        """Return image URL for AUDIO posts as cover image"""
        request = self.context.get('request')
        if obj.type == 'AUDIO' and obj.image and hasattr(obj.image, 'url'):
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None

    def get_audio_url(self, obj):
        request = self.context.get('request')
        if obj.audio_file and hasattr(obj.audio_file, 'url'):
            return request.build_absolute_uri(obj.audio_file.url) if request else obj.audio_file.url
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Remove the raw image path if we have the URL
        if data['type'] == 'NEWS' and data['image_url']:
            data.pop('image', None)
            data.pop('cover_image_url', None)  # Remove cover_image_url for NEWS posts
        elif data['type'] == 'AUDIO' and data['cover_image_url']:
            data.pop('image', None)
            data.pop('image_url', None)  # Remove image_url for AUDIO posts
        if data['audio_url']:
            data.pop('audio_file', None)
        return data

    def validate(self, data):
        """Custom validation for post creation/update"""
        if not data.get('type'):
            raise serializers.ValidationError({'type': 'Post type is required'})
        if not data.get('title'):
            raise serializers.ValidationError({'title': 'Title is required'})

        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError('Authentication required')

        if data.get('type') == 'AUDIO':
            if not self.instance:  # Creating new post
                if not request.FILES.get('image'):
                    raise serializers.ValidationError({'image': 'Cover image is required for audio posts'})
                if not request.FILES.get('audio_file'):
                    raise serializers.ValidationError({'audio_file': 'Audio file is required for audio posts'})

        return data

    def create(self, validated_data):
        # Ensure author is set from the request
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)

class PostInteractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostInteraction
        fields = ('id', 'user', 'post', 'interaction_type', 'created_at')
        read_only_fields = ('user',)

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data) 