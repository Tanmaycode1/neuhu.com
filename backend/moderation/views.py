from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import Report, ContentFilter
from .serializers import ReportSerializer, ContentFilterSerializer
import re

class ReportViewSet(viewsets.ModelViewSet):
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Report.objects.all()
        return Report.objects.filter(reporter=self.request.user)

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def resolve(self, request, pk=None):
        report = self.get_object()
        resolution = request.data.get('resolution', '')
        status = request.data.get('status', 'RESOLVED')

        report.status = status
        report.resolution_note = resolution
        report.resolved_by = request.user
        report.save()

        return Response({
            'status': 'report resolved',
            'resolution': resolution
        })

class ContentFilterViewSet(viewsets.ModelViewSet):
    queryset = ContentFilter.objects.all()
    serializer_class = ContentFilterSerializer
    permission_classes = [IsAdminUser]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['post'])
    def filter_content(self, request):
        content = request.data.get('content', '')
        filters = ContentFilter.objects.filter(is_active=True)

        filtered_content = content
        for content_filter in filters:
            if content_filter.is_regex:
                filtered_content = re.sub(
                    content_filter.keyword,
                    content_filter.replacement or '*' * len(content_filter.keyword),
                    filtered_content
                )
            else:
                filtered_content = filtered_content.replace(
                    content_filter.keyword,
                    content_filter.replacement or '*' * len(content_filter.keyword)
                )

        return Response({
            'original_content': content,
            'filtered_content': filtered_content
        })
