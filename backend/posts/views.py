from django.shortcuts import render
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import Post, Comment, PostInteraction, TrendingScore
from .serializers import (
    PostSerializer, 
    CommentSerializer,
    PostInteractionSerializer
)
from django.core.files.storage import default_storage
from core.utils import handle_uploaded_file
from django.shortcuts import get_object_or_404
from users.serializers import UserSerializer
from django.db.models import F, Count, ExpressionWrapper, FloatField, Q
from django.db.models.functions import Now
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache
from core.decorators import cache_response
from chat.models import ChatRoom, Message
import json
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from core.decorators import handle_exceptions
from core.utils import handle_uploaded_file
from core.views import BaseViewSet
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

class PostViewSet(BaseViewSet):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type', 'author']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'likes_count']
    model_name = 'post'

    def get_queryset(self):
        queryset = Post.objects.all()
        following = self.request.query_params.get('following', None)
        if following == 'true':
            queryset = queryset.filter(author__in=self.request.user.following.all())
        return queryset

    @handle_exceptions
    def perform_create(self, serializer):
        # Handle media file if present
        media_file = self.request.FILES.get('media')
        if media_file:
            media_path = handle_uploaded_file(
                media_file, 
                directory='posts'
            )
            serializer.save(
                author=self.request.user,
                media=media_path
            )
        else:
            serializer.save(author=self.request.user)
        # Invalidate relevant caches
        cache.delete_pattern('*feed*')
        cache.delete_pattern('*trending*')
        cache.delete('trending_posts')  # Invalidate trending cache

    def perform_update(self, serializer):
        audio_file = self.request.FILES.get('audio_file')
        if audio_file:
            # Delete old file if it exists
            instance = self.get_object()
            if instance.audio_file:
                default_storage.delete(instance.audio_file.name)
            
            file_path = handle_uploaded_file(audio_file, 'audio')
            serializer.save(audio_file=file_path)
        else:
            serializer.save()
        # Invalidate relevant caches
        cache.delete_pattern(f'post:{instance.id}*')
        cache.delete_pattern('*feed*')
        cache.delete_pattern('*trending*')
        cache.delete('trending_posts')  # Invalidate trending cache

    def perform_destroy(self, instance):
        # Delete associated file when deleting the post
        if instance.audio_file:
            default_storage.delete(instance.audio_file.name)
        # Invalidate relevant caches before deletion
        cache.delete_pattern(f'post:{instance.id}*')
        cache.delete_pattern('*feed*')
        cache.delete_pattern('*trending*')
        cache.delete('trending_posts')  # Invalidate trending cache
        instance.delete()

    @swagger_auto_schema(
        operation_description="Get list of posts with optional filtering",
        manual_parameters=[
            openapi.Parameter(
                'type', 
                openapi.IN_QUERY,
                description="Filter by post type (NEWS/AUDIO)",
                type=openapi.TYPE_STRING,
                enum=['NEWS', 'AUDIO']
            ),
            openapi.Parameter(
                'following', 
                openapi.IN_QUERY,
                description="Filter posts from followed users",
                type=openapi.TYPE_BOOLEAN
            ),
        ],
        responses={
            200: PostSerializer(many=True),
            400: 'Bad Request',
            401: 'Unauthorized'
        }
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Create a new post",
        request_body=PostSerializer,
        responses={
            201: PostSerializer,
            400: 'Bad Request',
            401: 'Unauthorized'
        }
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Like or unlike a post",
        responses={
            200: openapi.Response(
                description="Success response",
                examples={
                    "application/json": {
                        "status": "liked/unliked"
                    }
                }
            )
        }
    )
    @action(detail=True, methods=['POST'])
    def like(self, request, pk=None):
        """Like or unlike a post"""
        post = self.get_object()
        user = request.user
        
        if user in post.likes.all():
            # Unlike
            post.likes.remove(user)
            # Remove like interaction
            PostInteraction.objects.filter(
                user=user,
                post=post,
                interaction_type='LIKE'
            ).delete()
            liked = False
        else:
            # Like
            post.likes.add(user)
            # Create like interaction
            PostInteraction.objects.create(
                user=user,
                post=post,
                interaction_type='LIKE'
            )
            liked = True

        # Update trending score
        self.update_trending_score(post)

        # Invalidate relevant caches
        cache.delete(f'post:{post.id}')
        cache.delete(f'user_feed:{request.user.id}')
        cache.delete('trending_posts')

        return Response({
            'status': 'success',
            'liked': liked,
            'likes_count': post.likes.count()
        })

    @swagger_auto_schema(
        operation_description="Get personalized feed",
        responses={200: PostSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def feed(self, request):
        """Get personalized feed for the current user"""
        # Get posts from users that the current user follows
        following_posts = Post.objects.filter(
            author__in=request.user.following.all()
        ).order_by('-created_at')

        # Get trending posts
        trending_posts = Post.objects.filter(
            trending_score__score__gt=0
        ).order_by('-trending_score__score')

        # Combine and remove duplicates
        feed_posts = (following_posts | trending_posts).distinct()

        # Apply any additional filtering
        feed_posts = self.filter_queryset(feed_posts)

        # Paginate results
        page = self.paginate_queryset(feed_posts)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(feed_posts, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def comments(self, request, pk=None):
        post = self.get_object()
        comments = post.comments.all().order_by('-created_at')
        page = self.paginate_queryset(comments)
        if page is not None:
            serializer = CommentSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def comment(self, request, pk=None):
        """Add a comment to a post"""
        post = self.get_object()
        serializer = CommentSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save(
                author=request.user,
                post=post
            )
            # Update trending score after comment
            self.update_trending_score(post)
            
            # Invalidate relevant caches
            cache.delete(f'post:{post.id}')
            cache.delete(f'user_feed:{request.user.id}')
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def likers(self, request, pk=None):
        post = self.get_object()
        page = self.paginate_queryset(post.likes.all())
        if page is not None:
            serializer = UserSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = UserSerializer(post.likes.all(), many=True)
        return Response(serializer.data)

    @method_decorator(cache_page(300))  # Cache for 5 minutes
    @action(detail=False, methods=['get'])
    def trending(self, request):
        """Get trending posts with caching"""
        cache_key = 'trending_posts'
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return Response(cached_data)

        posts = Post.objects.filter(
            trending_score__score__gt=0
        ).order_by('-trending_score__score')

        posts = self.filter_queryset(posts)
        page = self.paginate_queryset(posts)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response_data = self.get_paginated_response(serializer.data).data
        else:
            serializer = self.get_serializer(posts, many=True)
            response_data = serializer.data

        # Cache the serialized data
        cache.set(cache_key, response_data, timeout=300)  # 5 minutes cache

        return Response(response_data)

    @action(detail=True, methods=['post'])
    def record_interaction(self, request, pk=None):
        """Record user interaction with a post"""
        post = self.get_object()
        interaction_type = request.data.get('type', 'VIEW')

        # Record interaction
        PostInteraction.objects.get_or_create(
            post=post,
            user=request.user,
            interaction_type=interaction_type
        )

        # Update trending score
        self.update_trending_score(post)

        return Response({'status': 'interaction recorded'})

    def update_trending_score(self, post):
        """Update the trending score for a post"""
        try:
            trending_score = post.trending_score
        except TrendingScore.DoesNotExist:
            trending_score = TrendingScore.objects.create(post=post)

        # Update counts
        trending_score.like_count = post.likes.count()
        trending_score.comment_count = post.comments.count()
        trending_score.share_count = PostInteraction.objects.filter(
            post=post,
            interaction_type='SHARE'
        ).count()

        # Calculate score based on interactions
        time_diff = timezone.now() - post.created_at
        hours_since_posted = time_diff.total_seconds() / 3600

        # Simple trending score formula
        score = (
            trending_score.like_count * 1.5 +
            trending_score.comment_count * 2.0 +
            trending_score.share_count * 2.5
        ) / (hours_since_posted + 2) ** 1.8

        trending_score.score = score
        trending_score.save()

    @action(detail=True, methods=['post'])
    def share(self, request, pk=None):
        """Share post to a chat room"""
        post = self.get_object()
        room_id = request.data.get('room_id')
        message_text = request.data.get('message', '')

        try:
            room = ChatRoom.objects.get(
                id=room_id,
                participants=request.user
            )
        except ChatRoom.DoesNotExist:
            return Response(
                {'error': 'Chat room not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Create a message with the shared post
        shared_content = {
            'type': 'shared_post',
            'post_id': str(post.id),
            'title': post.title,
            'message': message_text
        }

        message = Message.objects.create(
            room=room,
            sender=request.user,
            content=json.dumps(shared_content)
        )

        # Record share interaction
        PostInteraction.objects.get_or_create(
            post=post,
            user=request.user,
            interaction_type='SHARE'
        )

        # Update trending score
        self.update_trending_score(post)

        # Invalidate relevant caches
        cache.delete(f'user_feed:{request.user.id}')
        cache.delete('trending_posts')

        return Response({
            'status': 'post shared',
            'message_id': str(message.id)
        })

    @action(detail=True, methods=['delete'])
    def delete_comment(self, request, pk=None):
        """Delete a comment on a post"""
        comment_id = request.data.get('comment_id')
        try:
            comment = Comment.objects.get(
                id=comment_id,
                post_id=pk,
                author=request.user
            )
            comment.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Comment.DoesNotExist:
            return Response(
                {'error': 'Comment not found or unauthorized'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['put'])
    def edit_comment(self, request, pk=None):
        """Edit a comment on a post"""
        comment_id = request.data.get('comment_id')
        content = request.data.get('content')

        try:
            comment = Comment.objects.get(
                id=comment_id,
                post_id=pk,
                author=request.user
            )
            comment.content = content
            comment.save()
            return Response(CommentSerializer(comment).data)
        except Comment.DoesNotExist:
            return Response(
                {'error': 'Comment not found or unauthorized'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['get'])
    def user_interaction(self, request, pk=None):
        """Get current user's interaction with the post"""
        post = self.get_object()
        interactions = PostInteraction.objects.filter(
            post=post,
            user=request.user
        ).values_list('interaction_type', flat=True)
        
        return Response({
            'is_liked': request.user in post.likes.all(),
            'has_commented': post.comments.filter(author=request.user).exists(),
            'interactions': list(interactions)
        })

    @action(detail=False)
    def search(self, request):
        query = request.query_params.get('q', '')
        if not query:
            return Response([])

        posts = self.get_queryset().filter(
            Q(content__icontains=query) |
            Q(author__username__icontains=query)
        ).select_related('author').prefetch_related('likes')

        serializer = self.get_serializer(posts, many=True)
        return Response(serializer.data)

class CommentViewSet(BaseViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]
    model_name = 'comment'

class PostInteractionViewSet(BaseViewSet):
    queryset = PostInteraction.objects.all()
    serializer_class = PostInteractionSerializer
    permission_classes = [IsAuthenticated]
    model_name = 'postinteraction'
