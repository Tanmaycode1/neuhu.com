from django.shortcuts import render, get_object_or_404
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.core.exceptions import ValidationError
from django.db.models import F, Count, ExpressionWrapper, FloatField, Case, When, Exists, OuterRef, Q
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
import json
from rest_framework.exceptions import PermissionDenied
from django.db import models

from .models import Post, Comment, PostInteraction, TrendingScore
from .serializers import PostSerializer, CommentSerializer, PostInteractionSerializer
from users.serializers import UserSerializer
# from chat.models import ChatRoom, Message
from core.decorators import handle_exceptions, cache_response
from core.utils import handle_uploaded_file
from core.views import BaseViewSet

class PostViewSet(BaseViewSet):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type', 'author']
    ordering_fields = ['created_at', 'likes_count', 'comments_count']
    model_name = 'post'

    def get_permissions(self):
        """
        Override to set custom permissions per action
        """
        if self.action in ['list', 'retrieve', 'feed', 'trending']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = Post.objects.select_related('author', 'trending_score')\
            .prefetch_related('likes', 'comments')\
            .annotate(
                likes_count=Count('likes', distinct=True),
                comments_count=Count('comments', distinct=True)
            ).order_by('-created_at')  # Add default ordering
        
        if self.request.user.is_authenticated:
            queryset = queryset.annotate(
                is_liked=Exists(
                    Post.likes.through.objects.filter(
                        post_id=OuterRef('pk'),
                        user_id=self.request.user.id
                    )
                )
            )
        else:
            # For unauthenticated users, set is_liked to False
            queryset = queryset.annotate(
                is_liked=Case(
                    When(pk__isnull=False, then=False),
                    default=False,
                    output_field=models.BooleanField(),
                )
            )
        
        following = self.request.query_params.get('following', None)
        if following == 'true' and self.request.user.is_authenticated:
            queryset = queryset.filter(author__in=self.request.user.following.all())
            
        return queryset

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            post = self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            
            # Re-serialize the post to include all fields
            response_serializer = self.get_serializer(post)
            
            return Response({
                'success': True,
                'data': response_serializer.data
            }, status=status.HTTP_201_CREATED, headers=headers)
            
        except ValidationError as e:
            return Response({
                'success': False,
                'error': str(e),
                'errors': e.detail if hasattr(e, 'detail') else None
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @handle_exceptions
    def perform_create(self, serializer):
        """Create a new post with media handling"""
        try:
            # Get files and post type
            image = self.request.FILES.get('image')
            audio_file = self.request.FILES.get('audio_file')
            post_type = self.request.data.get('type')

            # Debug logging
            print("Creating post:", {
                'type': post_type,
                'title': self.request.data.get('title'),
                'has_image': bool(image),
                'has_audio': bool(audio_file),
                'data': dict(self.request.data),
                'user': self.request.user.id  # Log the user ID
            })

            # Handle media files
            image_path = None
            audio_path = None

            if image:
                try:
                    if not image.content_type.startswith('image/'):
                        raise ValidationError('Invalid image file type')
                    image_path = handle_uploaded_file(image, 'posts/images')
                except Exception as e:
                    print("Image processing error:", str(e))
                    raise ValidationError(f'Error processing image: {str(e)}')

            if audio_file:
                try:
                    if not audio_file.content_type.startswith('audio/'):
                        raise ValidationError('Invalid audio file type')
                    audio_path = handle_uploaded_file(audio_file, 'posts/audio')
                except Exception as e:
                    print("Audio processing error:", str(e))
                    if image_path:
                        default_storage.delete(image_path)
                    raise ValidationError(f'Error processing audio: {str(e)}')

            # Create post with media paths
            post = serializer.save(
                author=self.request.user,  # Explicitly set the author
                image=image_path,
                audio_file=audio_path
            )
            
            # Create trending score
            TrendingScore.objects.create(post=post)
            
            return post

        except Exception as e:
            print("Final error in perform_create:", str(e))
            # Cleanup any uploaded files
            if image_path:
                default_storage.delete(image_path)
            if audio_path:
                default_storage.delete(audio_path)
            raise ValidationError(str(e))
        
    @handle_exceptions
    def perform_update(self, serializer):
        """Update post with media handling"""
        instance = self.get_object()
        image = self.request.FILES.get('image')
        audio_file = self.request.FILES.get('audio_file')

        # Handle image update
        if image:
            if instance.image:
                default_storage.delete(instance.image.name)
            image_path = handle_uploaded_file(image, 'posts/images')
            serializer.save(image=image_path)

        # Handle audio update
        if audio_file:
            if instance.audio_file:
                default_storage.delete(instance.audio_file.name)
            audio_path = handle_uploaded_file(audio_file, 'posts/audio')
            serializer.save(audio_file=audio_path)

        serializer.save()
        self._invalidate_post_caches(instance.id)

    @handle_exceptions
    def perform_destroy(self, instance):
        """Delete post and associated media"""
        if instance.image:
            default_storage.delete(instance.image.name)
        if instance.audio_file:
            default_storage.delete(instance.audio_file.name)
            
        self._invalidate_post_caches(instance.id)
        instance.delete()

    @action(detail=False, methods=['get'])
    @method_decorator(cache_page(300))  # Cache for 5 minutes
    def feed(self, request):
        """Enhanced personalized feed with support for unauthenticated users"""
        try:
            # Get base queryset
            queryset = self.get_queryset()
            feed_posts = None

            if request.user.is_authenticated:
                # First try: Get posts from followed users (higher weight)
                following_posts = queryset.filter(
                    author__in=request.user.following.all()
                ).annotate(
                    relevance_score=ExpressionWrapper(
                        (F('trending_score__score') * 1.5) +
                        (F('likes_count') * 0.5) +
                        (F('comments_count') * 0.3) +
                        Case(
                            When(created_at__gte=timezone.now() - timedelta(days=1), then=10),
                            When(created_at__gte=timezone.now() - timedelta(days=7), then=5),
                            default=1,
                            output_field=FloatField(),
                        ),
                        output_field=FloatField()
                    )
                )
                
                if following_posts.exists():
                    feed_posts = following_posts.order_by('-relevance_score', '-created_at')
            
            if not feed_posts or not feed_posts.exists():
                # Second try: Get trending posts
                trending_posts = queryset.filter(
                    trending_score__score__gt=0
                ).annotate(
                    relevance_score=ExpressionWrapper(
                        (F('trending_score__score') * 1.0) +
                        (F('likes_count') * 0.3) +
                        (F('comments_count') * 0.2) +
                        Case(
                            When(created_at__gte=timezone.now() - timedelta(days=1), then=5),
                            When(created_at__gte=timezone.now() - timedelta(days=7), then=3),
                            default=1,
                            output_field=FloatField(),
                        ),
                        output_field=FloatField()
                    )
                )
                
                if trending_posts.exists():
                    feed_posts = trending_posts.order_by('-relevance_score', '-created_at')
                else:
                    # Final fallback: Get most recent posts
                    feed_posts = queryset.order_by('-created_at')

            # Paginate results
            page = self.paginate_queryset(feed_posts)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(feed_posts, many=True)
            return Response({
                'success': True,
                'data': {
                    'results': serializer.data,
                    'count': len(serializer.data)
                }
            })
        except Exception as e:
            print(f"Feed Error: {str(e)}")  # Debug log
            # Ultimate fallback: Get any recent posts
            try:
                fallback_posts = self.get_queryset().order_by('-created_at')[:10]
                serializer = self.get_serializer(fallback_posts, many=True)
                return Response({
                    'success': True,
                    'data': {
                        'results': serializer.data,
                        'count': len(serializer.data)
                    }
                })
            except Exception as inner_e:
                return Response({
                    'success': False,
                    'error': str(inner_e)
                }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
     """Like/unlike a post"""
     post = self.get_object()
     user = request.user
    
     if user in post.likes.all():
        post.likes.remove(user)
        return Response({
            'success': True, 
            'message': 'Post unliked',
            'liked': False
        })
     else:
        post.likes.add(user)
        # Create notification if post is not by the liker
        if post.author != user:
            post.author.create_like_notification(
                liker=user,
                post=post
            )
        return Response({
            'success': True, 
            'message': 'Post liked',
            'liked': True
        })

    @action(detail=True, methods=['get', 'post'], url_path='comments')
    def comments(self, request, pk=None):
        """Get or add comments for a post"""
        try:
            post = self.get_object()
            
            if request.method == 'GET':
                # Allow anyone to view comments
                comments = Comment.objects.filter(post=post)\
                    .select_related('author')\
                    .order_by('-created_at')

                serializer = CommentSerializer(
                    comments,
                    many=True,
                    context={'request': request}
                )
                
                return Response({
                    'success': True,
                    'data': serializer.data
                })
            else:  # POST
                # Require authentication for posting comments
                if not request.user.is_authenticated:
                    return Response({
                        'success': False,
                        'error': 'Authentication required'
                    }, status=status.HTTP_401_UNAUTHORIZED)
                
                # Get content from request data
                content = request.data.get('content')
                if not content:
                    return Response({
                        'success': False,
                        'error': 'Content is required'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Create the comment
                comment = Comment.objects.create(
                    post=post,
                    author=request.user,
                    content=content
                )
                
                # Return the serialized comment
                serializer = CommentSerializer(
                    comment,
                    context={'request': request}
                )
                
                return Response({
                    'success': True,
                    'data': serializer.data
                })
                
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def likers(self, request, pk=None):
        """Get users who liked the post"""
        post = self.get_object()
        page = self.paginate_queryset(post.likes.all())
        
        if page is not None:
            serializer = UserSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = UserSerializer(post.likes.all(), many=True)
        return Response(serializer.data)

    # @action(detail=True, methods=['post'])
    # def share(self, request, pk=None):
    #     """Share post to a chat room"""
    #     post = self.get_object()
    #     room_id = request.data.get('room_id')
    #     message_text = request.data.get('message', '')

    #     try:
    #         room = ChatRoom.objects.get(
    #             id=room_id,
    #             participants=request.user
    #         )
    #     except ChatRoom.DoesNotExist:
    #         return Response(
    #             {'error': 'Chat room not found or access denied'},
    #             status=status.HTTP_404_NOT_FOUND
    #         )

    #     # Create share message with more post details
    #     shared_content = {
    #         'type': 'shared_post',
    #         'post_id': str(post.id),
    #         'title': post.title,
    #         'description': post.description,
    #         'image_url': post.image.url if post.image else None,
    #         'author': {
    #             'username': post.author.username,
    #             'profile_image': post.author.profile_image.url if post.author.profile_image else None
    #         },
    #         'message': message_text
    #     }

    #     message = Message.objects.create(
    #         room=room,
    #         sender=request.user,
    #         content=json.dumps(shared_content)
    #     )

    #     # Record share interaction
    #     interaction, created = PostInteraction.objects.get_or_create(
    #         post=post,
    #         user=request.user,
    #         interaction_type='SHARE'
    #     )

    #     self._update_trending_score(post)
    #     self._invalidate_post_caches(post.id)

    #     return Response({
    #         'success': True,
    #         'data': {
    #             'message_id': str(message.id),
    #             'shared_content': shared_content
    #         }
    #     })

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

    @action(detail=False, methods=['get'])
    def trending(self, request):
        """Get trending posts or recent posts"""
        try:
            # Get all NEWS posts, ordered by created_at as a fallback
            posts = self.get_queryset().filter(type='NEWS').order_by('-created_at')
            print(f"Found {posts.count()} NEWS posts")  # Debug log
            
            # Try to get posts with trending scores first
            trending_posts = posts.exclude(trending_score=None)\
                .order_by('-trending_score__score')[:10]
            print(f"Found {trending_posts.count()} trending posts")  # Debug log
            
            # If no trending posts, get recent posts
            if not trending_posts.exists():
                print("No trending posts found, using recent posts")  # Debug log
                trending_posts = posts[:10]
            
            serializer = self.get_serializer(trending_posts, many=True)
            response_data = {
                'success': True,
                'data': {
                    'results': serializer.data,
                    'count': len(serializer.data)
                }
            }
            print(f"Returning {len(serializer.data)} posts")  # Debug log
            return Response(response_data)
        except Exception as e:
            print(f"Error in trending endpoint: {str(e)}")  # Debug log
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['GET'])
    def my_posts(self, request):
        """Get posts created by the current user"""
        try:
            # Get posts by current user
            posts = self.get_queryset().filter(author=request.user)
            
            # Apply pagination
            page = self.paginate_queryset(posts)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(posts, many=True)
            return Response({
                'success': True,
                'data': serializer.data
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['PUT'])
    def edit_comment(self, request, pk=None):
        """Edit a comment on the post"""
        try:
            comment_id = request.data.get('comment_id')
            content = request.data.get('content')
            
            if not comment_id or not content:
                return Response({
                    'success': False,
                    'error': 'comment_id and content are required'
                }, status=status.HTTP_400_BAD_REQUEST)

            comment = Comment.objects.get(id=comment_id, post_id=pk)
            
            # Check if user is the author of the comment
            if comment.author != request.user:
                return Response({
                    'success': False,
                    'error': 'You can only edit your own comments'
                }, status=status.HTTP_403_FORBIDDEN)

            comment.content = content
            comment.save()

            serializer = CommentSerializer(
                comment,
                context={'request': request}
            )
            
            return Response({
                'success': True,
                'data': serializer.data
            })
        except Comment.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Comment not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['DELETE'])
    def delete_comment(self, request, pk=None):
        """Delete a comment from the post"""
        try:
            comment_id = request.data.get('comment_id')
            
            if not comment_id:
                return Response({
                    'success': False,
                    'error': 'comment_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            comment = Comment.objects.get(id=comment_id, post_id=pk)
            
            # Check if user is the author of the comment
            if comment.author != request.user:
                return Response({
                    'success': False,
                    'error': 'You can only delete your own comments'
                }, status=status.HTTP_403_FORBIDDEN)

            comment.delete()
            
            return Response({
                'success': True,
                'message': 'Comment deleted successfully'
            })
        except Comment.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Comment not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    def _update_trending_score(self, post):
        """Update post's trending score"""
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

        # Calculate score based on time decay
        time_diff = timezone.now() - post.created_at
        hours_since_posted = time_diff.total_seconds() / 3600

        # Enhanced trending score formula
        score = (
            trending_score.like_count * 1.5 +
            trending_score.comment_count * 2.0 +
            trending_score.share_count * 2.5
        ) / (hours_since_posted + 2) ** 1.8

        trending_score.score = score
        trending_score.save()

    def _invalidate_post_caches(self, post_id=None):
        """Invalidate relevant caches"""
        if post_id:
            cache.delete(f'post:{post_id}')
        cache.delete_pattern('*feed*')
        cache.delete_pattern('*trending*')
        cache.delete('trending_posts')

    @action(detail=False, methods=['GET'])
    def user_posts(self, request):
        """Get all posts by a specific user"""
        try:
            user_id = request.query_params.get('user_id')
            post_type = request.query_params.get('type')  # Optional filter by post type
            
            if not user_id:
                return Response({
                    'success': False,
                    'error': 'user_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Get base queryset for the user
            queryset = self.get_queryset().filter(author_id=user_id)
            
            # Apply type filter if provided
            if post_type:
                queryset = queryset.filter(type=post_type.upper())

            # Apply pagination
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True)
            return Response({
                'success': True,
                'data': {
                    'results': serializer.data,
                    'count': len(serializer.data)
                }
            })

        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['GET'])
    @method_decorator(cache_page(300))  # Cache for 5 minutes
    def highlights(self, request):
        """Get highlights: latest news, trending audio, and a random post"""
        try:
            # Get latest news post
            latest_news = self.get_queryset().filter(type='NEWS').order_by('-created_at').first()
            
            # Get trending audio post
            trending_audio = self.get_queryset().filter(type='AUDIO')\
                .exclude(trending_score=None)\
                .order_by('-trending_score__score', '-created_at').first()
            
            # If no trending audio, get latest audio
            if not trending_audio:
                trending_audio = self.get_queryset().filter(type='AUDIO')\
                    .order_by('-created_at').first()
            
            # Get a random post (excluding the ones already selected)
            excluded_ids = [p.id for p in [latest_news, trending_audio] if p]
            random_post = self.get_queryset().exclude(id__in=excluded_ids)\
                .order_by('?').first()
            
            # Serialize the posts
            serializer = self.get_serializer([
                post for post in [latest_news, trending_audio, random_post] 
                if post is not None
            ], many=True)
            
            # Format response with categories
            response_data = {
                'success': True,
                'data': {
                    'latest_news': serializer.data[0] if latest_news else None,
                    'trending_audio': serializer.data[1] if trending_audio else None,
                    'featured_post': serializer.data[2] if random_post else None
                }
            }
            
            return Response(response_data)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

class CommentViewSet(BaseViewSet):
    queryset = Comment.objects.select_related('author', 'post').order_by('-created_at')
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]
    model_name = 'comment'

    def get_serializer_context(self):
        """Add request to serializer context"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        return Comment.objects.select_related('author', 'post').order_by('-created_at')

    def perform_create(self, serializer):
        """Create a new comment"""
        comment = serializer.save(author=self.request.user)
        # Return the serialized comment with context
        return self.get_serializer(comment, context={'request': self.request}).data

    @action(detail=True, methods=['PUT'])
    def edit(self, request, pk=None):
        """Edit a comment"""
        comment = self.get_object()
        
        if comment.author != request.user:
            raise PermissionDenied("You can't edit this comment")
            
        serializer = self.get_serializer(
            comment, 
            data=request.data, 
            partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        comment = serializer.save()
        
        # Return the updated comment with proper context
        return Response({
            'success': True,
            'data': self.get_serializer(comment, context={'request': request}).data
        })

    @action(detail=True, methods=['DELETE'])
    def delete(self, request, pk=None):
        """Delete a comment"""
        comment = self.get_object()
        
        if comment.author != request.user:
            raise PermissionDenied("You can't delete this comment")
            
        comment.delete()
        
        # Update post's comment count
        post = comment.post
        post.comments_count = F('comments_count') - 1
        post.save()
        
        return Response({
            'success': True,
            'message': 'Comment deleted successfully'
        })

    @action(detail=True, methods=['POST'])
    def like(self, request, pk=None):
        """Like/Unlike a comment"""
        comment = self.get_object()
        
        if request.user in comment.likes.all():
            comment.likes.remove(request.user)
            liked = False
        else:
            comment.likes.add(request.user)
            liked = True
            
        return Response({
            'success': True,
            'data': {
                'liked': liked,
                'likes_count': comment.likes.count()
            }
        })

    @action(detail=True, methods=['get'])
    def replies(self, request, pk=None):
        """Get replies to a comment"""
        comment = self.get_object()
        replies = comment.replies.select_related('author').order_by('-created_at')
        
        page = self.paginate_queryset(replies)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(replies, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reply(self, request, pk=None):
        """Add a reply to a comment"""
        parent_comment = self.get_object()
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            reply = serializer.save(
                author=request.user,
                parent_comment=parent_comment,
                post=parent_comment.post
            )
            
            # Update post's trending score
            post_viewset = PostViewSet()
            post_viewset._update_trending_score(parent_comment.post)
            
            return Response(self.get_serializer(reply).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def thread(self, request, pk=None):
        """Get full comment thread including parent and all replies"""
        comment = self.get_object()
        
        # If this is a reply, get its parent comment
        if comment.parent_comment:
            parent = comment.parent_comment
        else:
            parent = comment
            
        # Get all replies in thread
        replies = parent.replies.select_related('author').order_by('created_at')
        
        thread_data = {
            'parent': self.get_serializer(parent).data,
            'replies': self.get_serializer(replies, many=True).data
        }
        
        return Response(thread_data)

    @action(detail=False, methods=['GET'])
    def post_comments(self, request):
        """Get comments for a post"""
        post_id = request.query_params.get('post_id')
        if not post_id:
            return Response({
                'success': False,
                'error': 'post_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        comments = self.get_queryset().filter(post_id=post_id)
        serializer = self.get_serializer(
            comments, 
            many=True,
            context={'request': request}
        )
        
        return Response({
            'success': True,
            'data': serializer.data
        })

class PostInteractionViewSet(BaseViewSet):
    queryset = PostInteraction.objects.select_related('user', 'post')
    serializer_class = PostInteractionSerializer
    permission_classes = [IsAuthenticated]
    model_name = 'postinteraction'
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['post', 'interaction_type']

    def get_queryset(self):
        return PostInteraction.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Create a new interaction"""
        # Check if interaction already exists
        existing = PostInteraction.objects.filter(
            user=self.request.user,
            post=serializer.validated_data['post'],
            interaction_type=serializer.validated_data['interaction_type']
        ).first()
        
        if existing:
            raise ValidationError('Interaction already exists')
            
        serializer.save(user=self.request.user)
        
        # Update post's trending score
        post = serializer.validated_data['post']
        post_viewset = PostViewSet()
        post_viewset._update_trending_score(post)

    def perform_destroy(self, instance):
        """Remove an interaction"""
        if instance.user != self.request.user:
            raise ValidationError("Cannot delete another user's interaction")
            
        post = instance.post
        instance.delete()
        
        # Update post's trending score
        post_viewset = PostViewSet()
        post_viewset._update_trending_score(post)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get interaction statistics for the current user"""
        stats = {
            'likes_given': PostInteraction.objects.filter(
                user=request.user,
                interaction_type='LIKE'
            ).count(),
            'posts_shared': PostInteraction.objects.filter(
                user=request.user,
                interaction_type='SHARE'
            ).count(),
            'posts_saved': PostInteraction.objects.filter(
                user=request.user,
                interaction_type='SAVE'
            ).count(),
            'total_interactions': PostInteraction.objects.filter(
                user=request.user
            ).count(),
        }
        return Response(stats)

    @action(detail=False, methods=['get'])
    def saved_posts(self, request):
        """Get all posts saved by the current user"""
        saved_interactions = self.get_queryset().filter(
            interaction_type='SAVE'
        ).select_related('post', 'post__author')
        
        posts = [interaction.post for interaction in saved_interactions]
        
        page = self.paginate_queryset(posts)
        if page is not None:
            serializer = PostSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
            
        serializer = PostSerializer(posts, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get user's recent interactions"""
        recent_interactions = self.get_queryset()\
            .select_related('post', 'post__author')\
            .order_by('-created_at')[:10]
            
        serializer = self.get_serializer(recent_interactions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def post_stats(self, request, pk=None):
        """Get interaction statistics for a specific post"""
        interaction = self.get_object()
        post = interaction.post
        
        # Get interaction counts by type
        interaction_counts = PostInteraction.objects\
            .filter(post=post)\
            .values('interaction_type')\
            .annotate(count=Count('id'))
            
        stats = {
            item['interaction_type']: item['count'] 
            for item in interaction_counts
        }
        
        # Add additional stats
        stats.update({
            'total_interactions': sum(stats.values()),
            'unique_users': PostInteraction.objects\
                .filter(post=post)\
                .values('user')\
                .distinct()\
                .count()
        })
        
        return Response(stats)