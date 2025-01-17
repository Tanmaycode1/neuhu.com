from rest_framework import serializers
from .models import Post, Comment, TrendingScore, PostInteraction
from users.serializers import UserSerializer

class CommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    author_id = serializers.UUIDField(write_only=True, required=False)
    
    class Meta:
        model = Comment
        fields = ('id', 'author', 'author_id', 'content', 'created_at', 'updated_at')
        read_only_fields = ('author',)

    def create(self, validated_data):
        validated_data.pop('author_id', None)
        return super().create(validated_data)

class TrendingScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrendingScore
        fields = ('score', 'view_count', 'like_count', 'comment_count', 'share_count')

class PostSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    likes_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    trending_data = TrendingScoreSerializer(source='trending_score', read_only=True)
    
    class Meta:
        model = Post
        fields = (
            'id', 'author', 'type', 'title', 'description', 
            'audio_file', 'created_at', 'updated_at', 
            'comments', 'comments_count', 'likes_count', 'is_liked', 'trending_data'
        )
        read_only_fields = ('author',)

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_comments_count(self, obj):
        return obj.comments.count()

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request and request.query_params.get('include_comments', '').lower() == 'true':
            data['comments'] = CommentSerializer(
                instance.comments.all().order_by('-created_at')[:10], 
                many=True
            ).data
        else:
            data.pop('comments', None)
        return data 

class PostInteractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostInteraction
        fields = ('id', 'user', 'post', 'interaction_type', 'created_at')
        read_only_fields = ('user',)

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data) 