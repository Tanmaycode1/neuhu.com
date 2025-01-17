from rest_framework import serializers
from .models import Report, ContentFilter
from users.serializers import UserSerializer

class ReportSerializer(serializers.ModelSerializer):
    reporter = UserSerializer(read_only=True)
    reported_user = UserSerializer(read_only=True)
    resolved_by = UserSerializer(read_only=True)

    class Meta:
        model = Report
        fields = '__all__'
        read_only_fields = ('status', 'resolved_by', 'resolution_note')

class ContentFilterSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = ContentFilter
        fields = '__all__'
        read_only_fields = ('created_by',) 