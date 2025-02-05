from django.shortcuts import render
from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.postgres.search import (
    SearchVector, SearchQuery, SearchRank, TrigramSimilarity
)
from django.db.models import Q, F, Value, Case, When, Exists, OuterRef
from django.db.models.functions import Greatest, Lower
from posts.models import Post, PostInteraction
from users.models import User
from posts.serializers import PostSerializer
from users.serializers import UserSerializer
from django.core.cache import cache
from .models import SearchLog, SearchQuery
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from rest_framework.decorators import action, api_view, permission_classes
import logging
from django.db.models import Prefetch

logger = logging.getLogger(__name__)

class SearchViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    def _log_search(self, user, query, results_count, search_type='ALL', ip_address=None):
        SearchLog.objects.create(
            user=user,
            query=query,
            results_count=results_count,
            search_type=search_type,
            ip_address=ip_address
        )

    def _search_users(self, query):
        """
        Enhanced user search with better relevance scoring and following status
        """
        try:
            # Calculate similarities
            username_similarity = TrigramSimilarity('username', query)
            name_similarity = Greatest(
                TrigramSimilarity('first_name', query),
                TrigramSimilarity('last_name', query)
            )
            
            # Get current user's following
            user_following = self.request.user.following.all()
            
            users = User.objects.exclude(
                id=self.request.user.id  # Exclude current user
            ).annotate(
                # Exact match score
                exact_match=Case(
                    When(username__iexact=query, then=Value(1.0)),
                    default=Value(0.0)
                ),
                # Contains score
                contains_score=Case(
                    When(username__icontains=query, then=Value(0.6)),
                    When(first_name__icontains=query, then=Value(0.5)),
                    When(last_name__icontains=query, then=Value(0.5)),
                    When(bio__icontains=query, then=Value(0.3)),
                    default=Value(0.0)
                ),
                # Similarity score
                similarity=Greatest(
                    username_similarity * 0.4,
                    name_similarity * 0.3
                ),
                # Final relevance score
                relevance=Greatest(
                    F('exact_match'),
                    F('contains_score'),
                    F('similarity')
                ),
                # Following status
                is_followed=Exists(
                    user_following.filter(id=OuterRef('id'))
                )
            ).select_related(
                'profile'
            ).filter(
                Q(relevance__gt=0.2)  # Adjust threshold as needed
            ).order_by('-relevance', 'username')[:20]

            serialized_data = UserSerializer(
                users,
                many=True,
                context={'request': self.request}
            ).data

            logger.info(f"Successfully searched users. Found {len(serialized_data)} results")
            return serialized_data

        except Exception as e:
            logger.error(f"Search users error: {str(e)}", exc_info=True)
            return []

    def _prepare_post_queryset(self, queryset):
        """Common method to prepare post queryset with user interactions"""
        user = self.request.user
        
        # Prefetch related data
        queryset = queryset.select_related(
            'author',
            'author__profile'
        ).prefetch_related(
            'comments',
            'interactions'  # Use interactions instead of likes
        )

        # Annotate user interactions
        queryset = queryset.annotate(
            is_liked=Exists(
                PostInteraction.objects.filter(
                    user=user,
                    post_id=OuterRef('id'),
                    interaction_type='LIKE'
                )
            ),
            is_saved=Exists(
                PostInteraction.objects.filter(
                    user=user,
                    post_id=OuterRef('id'),
                    interaction_type='SAVE'
                )
            )
        )

        return queryset

    def _search_posts(self, query):
        """Enhanced post search with user interactions"""
        try:
            # Calculate similarities
            title_similarity = TrigramSimilarity('title', query)
            desc_similarity = TrigramSimilarity('description', query)
            
            # Get current user's interactions
            user_interactions = PostInteraction.objects.filter(
                user=self.request.user,
                interaction_type='LIKE'
            )
            
            posts = Post.objects.annotate(
                exact_match=Case(
                    When(title__iexact=query, then=Value(1.0)),
                    default=Value(0.0)
                ),
                contains_score=Case(
                    When(title__icontains=query, then=Value(0.7)),
                    When(description__icontains=query, then=Value(0.5)),
                    default=Value(0.0)
                ),
                similarity=Greatest(
                    title_similarity * 0.4,
                    desc_similarity * 0.3
                ),
                relevance=Greatest(
                    F('exact_match'),
                    F('contains_score'),
                    F('similarity')
                ),
                is_liked=Exists(
                    user_interactions.filter(
                        post_id=OuterRef('id')
                    )
                )
            ).select_related(
                'author'
            ).filter(
                Q(relevance__gt=0.2)
            ).order_by('-relevance', '-created_at')[:20]

            serialized_data = PostSerializer(
                posts,
                many=True,
                context={'request': self.request}
            ).data

            logger.info(f"Successfully searched posts. Found {len(serialized_data)} results")
            return serialized_data

        except Exception as e:
            logger.error(f"Search posts error: {str(e)}", exc_info=True)
            return []

    def _get_trending_posts(self):
        """Get trending posts with user interactions"""
        posts = Post.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).annotate(
            trending_score=F('view_count') * 0.3 + 
                         F('like_count') * 0.5 + 
                         F('comment_count') * 0.2
        )

        # Apply common post preparations
        posts = self._prepare_post_queryset(posts)
        
        # Order by trending score
        posts = posts.order_by('-trending_score')[:20]
        
        return PostSerializer(
            posts,
            many=True,
            context={'request': self.request}
        ).data

    def _get_latest_posts(self):
        """Get latest posts with user interactions"""
        posts = Post.objects.all()
        
        # Apply common post preparations
        posts = self._prepare_post_queryset(posts)
        
        # Order by creation date
        posts = posts.order_by('-created_at')[:20]
        
        return PostSerializer(
            posts,
            many=True,
            context={'request': self.request}
        ).data

    def list(self, request):
        """Main search endpoint"""
        try:
            self.request = request
            query = request.GET.get('q', '').strip()
            search_type = request.GET.get('type', 'all').lower()

            logger.info(f"Search request - query: {query}, type: {search_type}")

            if not query:
                logger.info("Empty query, returning empty results")
                return Response({
                    'success': True,
                    'data': {
                        'posts': [],
                        'users': []
                    }
                })

            results = {
                'posts': [],
                'users': []
            }

            # Get posts if requested
            if search_type in ['all', 'posts']:
                try:
                    results['posts'] = self._search_posts(query)
                    logger.info(f"Found {len(results['posts'])} posts")
                except Exception as e:
                    logger.error(f"Error searching posts: {str(e)}", exc_info=True)

            # Get users if requested
            if search_type in ['all', 'users']:
                try:
                    results['users'] = self._search_users(query)
                    logger.info(f"Found {len(results['users'])} users")
                except Exception as e:
                    logger.error(f"Error searching users: {str(e)}", exc_info=True)

            return Response({
                'success': True,
                'data': results
            })

        except Exception as e:
            logger.error(f"Search error: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'message': "An error occurred while searching",
                'data': {
                    'posts': [],
                    'users': []
                }
            }, status=500)

    @action(detail=False, methods=['get'])
    def trending_searches(self, request):
        """Get trending searches from the last 7 days"""
        # Try to get from cache first
        cache_key = 'trending_searches'
        trending = cache.get(cache_key)
        
        if not trending:
            # Get trending searches from the last 7 days
            trending = SearchQuery.objects.filter(
                created_at__gte=timezone.now() - timedelta(days=7)
            ).values('query').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            # Format the response
            trending = [
                {
                    'query': item['query'],
                    'count': item['count']
                } for item in trending
            ]
            
            # Cache for 1 hour
            cache.set(cache_key, trending, 60 * 60)
        
        return Response({
            'success': True,
            'data': trending
        })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search(request):
    query = request.GET.get('q', '').strip()
    if query:
        # Track the search query
        SearchQuery.objects.create(
            query=query,
            user=request.user
        )
        # ... rest of your search logic ...
