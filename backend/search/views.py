from django.shortcuts import render
from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.postgres.search import (
    SearchVector, SearchQuery, SearchRank, TrigramSimilarity
)
from django.db.models import Q, F, Value, Case, When, Exists, OuterRef
from django.db.models.functions import Greatest, Lower
from posts.models import Post
from users.models import User
from posts.serializers import PostSerializer
from users.serializers import UserSerializer
from django.core.cache import cache
from .models import SearchLog
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from rest_framework.decorators import action
import logging

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
        # Normalize query
        query_lower = query.lower()
        
        # Create search vectors with weights
        name_vector = (
            SearchVector('username', weight='A') +
            SearchVector('first_name', weight='B') +
            SearchVector('last_name', weight='B') +
            SearchVector('bio', weight='C')
        )
        
        # Calculate similarities
        username_similarity = TrigramSimilarity('username', query)
        name_similarity = Greatest(
            TrigramSimilarity('first_name', query),
            TrigramSimilarity('last_name', query)
        )
        
        users = User.objects.exclude(
            id=self.request.user.id  # Exclude current user
        ).annotate(
            # Exact match score
            exact_match=Case(
                When(username__iexact=query, then=Value(1.0)),
                default=Value(0.0)
            ),
            # Starts with score
            starts_with=Case(
                When(username__istartswith=query, then=Value(0.9)),
                When(first_name__istartswith=query, then=Value(0.8)),
                When(last_name__istartswith=query, then=Value(0.8)),
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
                F('starts_with'),
                F('contains_score'),
                F('similarity')
            ),
            # Following status
            is_followed=Exists(
                self.request.user.following.filter(
                    id=OuterRef('id')
                )
            )
        ).filter(
            Q(relevance__gt=0.2)  # Adjust threshold as needed
        ).order_by('-relevance', 'username')[:20]  # Limit results
        
        # Use UserSerializer with proper context for full URLs
        serializer = UserSerializer(users, many=True, context={'request': self.request})
        return serializer.data

    def _search_posts(self, query):
        """
        Enhanced post search with better relevance scoring:
        1. Exact title matches
        2. Title starts with query
        3. Contains query in title/description
        4. Trigram similarity as fallback
        """
        # Create search vectors with weights
        content_vector = (
            SearchVector('title', weight='A') +
            SearchVector('description', weight='B') +
            SearchVector('author__username', weight='C')
        )
        
        # Calculate similarities
        title_similarity = TrigramSimilarity('title', query)
        desc_similarity = TrigramSimilarity('description', query)
        
        posts = Post.objects.annotate(
            # Exact match score
            exact_match=Case(
                When(title__iexact=query, then=Value(1.0)),
                default=Value(0.0)
            ),
            # Starts with score
            starts_with=Case(
                When(title__istartswith=query, then=Value(0.9)),
                default=Value(0.0)
            ),
            # Contains score
            contains_score=Case(
                When(title__icontains=query, then=Value(0.7)),
                When(description__icontains=query, then=Value(0.5)),
                default=Value(0.0)
            ),
            # Similarity score
            similarity=Greatest(
                title_similarity * 0.4,
                desc_similarity * 0.3
            ),
            # Final relevance score
            relevance=Greatest(
                F('exact_match'),
                F('starts_with'),
                F('contains_score'),
                F('similarity')
            )
        ).filter(
            Q(relevance__gt=0.2)  # Adjust threshold as needed
        ).order_by('-relevance', '-created_at')[:20]  # Limit results
        
        return posts

    def list(self, request):
        self.request = request
        query = request.GET.get('q', '').strip()
        search_type = request.GET.get('type', 'all').lower()
        bypass_cache = request.GET.get('bypass_cache') == '1'
        
        if not query:
            return Response({
                'success': False,
                'message': 'Query parameter is required',
                'data': {'posts': [], 'users': []}
            }, status=400)

        # Cache key based on query and type
        cache_key = f'search:{search_type}:{query}'
        
        # Get cached results only if not bypassing cache
        cached_results = None if bypass_cache else cache.get(cache_key)

        if cached_results:
            return Response({
                'success': True,
                'data': cached_results
            })

        results = {'posts': [], 'users': []}
        total_results = 0

        try:
            if search_type in ['all', 'posts']:
                posts = self._search_posts(query)
                results['posts'] = PostSerializer(posts, many=True).data
                total_results += posts.count()

            if search_type in ['all', 'users']:
                users = self._search_users(query)
                results['users'] = users
                total_results += len(users)

            # Log the search
            self._log_search(
                user=request.user,
                query=query,
                results_count=total_results,
                search_type=search_type.upper(),
                ip_address=request.META.get('REMOTE_ADDR')
            )

            # Cache results for 5 minutes
            cache.set(cache_key, results, 300)

            return Response({
                'success': True,
                'data': results
            })
            
        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            return Response({
                'success': False,
                'message': 'An error occurred while searching',
                'data': {'posts': [], 'users': []}
            }, status=500)

    @action(detail=False, methods=['get'])
    def trending(self, request):
        """Get trending searches from the last 7 days"""
        cache_key = 'trending_searches'
        cached_results = cache.get(cache_key)

        if cached_results:
            return Response({
                'success': True,
                'data': cached_results
            })

        try:
            trending = SearchLog.objects.filter(
                created_at__gte=timezone.now() - timedelta(days=7)
            ).values('query').annotate(
                count=Count('id'),
                last_searched=F('created_at')
            ).order_by('-count', '-last_searched')[:10]

            cache.set(cache_key, list(trending), 3600)  # Cache for 1 hour
            
            return Response({
                'success': True,
                'data': trending
            })
        except Exception as e:
            logger.error(f"Trending search error: {str(e)}")
            return Response({
                'success': False,
                'message': 'Failed to fetch trending searches'
            }, status=500)
