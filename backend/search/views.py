from django.shortcuts import render
from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.postgres.search import (
    SearchVector, SearchQuery, SearchRank, TrigramSimilarity
)
from django.db.models import Q, F
from django.db.models.functions import Greatest
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

    def _search_posts(self, query):
        # Create search vectors with weights
        search_vector = (
            SearchVector('title', weight='A') +
            SearchVector('description', weight='B') +
            SearchVector('author__username', weight='C')
        )
        
        # Create search query
        search_query = SearchQuery(query)
        
        # Calculate similarities
        title_similarity = TrigramSimilarity('title', query)
        description_similarity = TrigramSimilarity('description', query)
        
        # Combine full-text search with trigram similarity
        posts = Post.objects.annotate(
            search_rank=SearchRank(search_vector, search_query),
            similarity=Greatest(
                title_similarity * 0.4,  # Weight for title similarity
                description_similarity * 0.3  # Weight for description similarity
            )
        ).filter(
            Q(search_rank__gt=0.1) |  # Full-text search threshold
            Q(similarity__gt=0.1)      # Similarity search threshold
        ).order_by('-search_rank', '-similarity')
        
        return posts

    def _search_users(self, query):
        # Create search vectors with weights
        search_vector = (
            SearchVector('username', weight='A') +
            SearchVector('bio', weight='B') +
            SearchVector('first_name', weight='C') +
            SearchVector('last_name', weight='C')
        )
        
        # Create search query
        search_query = SearchQuery(query)
        
        # Calculate similarities
        username_similarity = TrigramSimilarity('username', query)
        name_similarity = Greatest(
            TrigramSimilarity('first_name', query),
            TrigramSimilarity('last_name', query)
        )
        
        # Combine full-text search with trigram similarity
        users = User.objects.annotate(
            search_rank=SearchRank(search_vector, search_query),
            similarity=Greatest(
                username_similarity * 0.6,  # Weight for username similarity
                name_similarity * 0.4       # Weight for name similarity
            )
        ).filter(
            Q(search_rank__gt=0.1) |  # Full-text search threshold
            Q(similarity__gt=0.1)      # Similarity search threshold
        ).order_by('-search_rank', '-similarity')
        
        return users

    def list(self, request):
        query = request.GET.get('q', '').strip()
        search_type = request.GET.get('type', 'all').lower()
        
        if not query:
            return Response({'error': 'Query parameter is required'}, status=400)

        # Cache key based on query and type
        cache_key = f'search:{search_type}:{query}'
        cached_results = cache.get(cache_key)

        if cached_results:
            return Response(cached_results)

        results = {'posts': [], 'users': []}
        total_results = 0

        if search_type in ['all', 'posts']:
            posts = self._search_posts(query)
            results['posts'] = PostSerializer(posts[:20], many=True).data
            total_results += posts.count()

        if search_type in ['all', 'users']:
            users = self._search_users(query)
            results['users'] = UserSerializer(users[:20], many=True).data
            total_results += users.count()

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

        return Response(results)

    @action(detail=False, methods=['get'])
    def trending(self, request):
        """Get trending searches from the last 7 days"""
        cache_key = 'trending_searches'
        cached_results = cache.get(cache_key)

        if cached_results:
            return Response(cached_results)

        trending = SearchLog.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).values('query').annotate(
            count=Count('id'),
            last_searched=F('created_at')
        ).order_by('-count', '-last_searched')[:10]

        cache.set(cache_key, list(trending), 3600)  # Cache for 1 hour
        return Response(trending)
