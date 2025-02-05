from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from users.models import User
from users.serializers import SearchUserSerializer

class ExploreViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def users(self, request):
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response({
                'success': True,
                'data': []
            })

        users = User.objects.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).exclude(id=request.user.id)[:10]

        serializer = SearchUserSerializer(users, many=True)
        return Response({
            'success': True,
            'data': serializer.data
        }) 