from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.conf import settings
from google.oauth2 import id_token
from google.auth.transport import requests
from users.models import UserProfile

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField()
    username = serializers.CharField(required=False)  # Make username optional
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ('email', 'password', 'username', 'first_name', 'last_name')

    def validate_email(self, value):
        try:
            user = User.objects.get(email=value)
            if user.email_verified and user.is_active:
                # If user exists, is verified and active, allow registration
                return value
            elif not user.email_verified:
                # If user exists but not verified, allow registration
                return value
            else:
                raise serializers.ValidationError('User with this email already exists')
        except User.DoesNotExist:
            return value

    def create(self, validated_data):
        if 'username' not in validated_data:
            validated_data['username'] = validated_data['email'].split('@')[0]
            
        user = User.objects.create_user(
            email=validated_data['email'],
            username=validated_data['username'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if not email or not password:
            raise serializers.ValidationError('Both email and password are required.')

        return attrs

class GoogleAuthSerializer(serializers.Serializer):
    token = serializers.CharField()
    
    def validate_token(self, value):
        try:
            # Verify the token
            idinfo = id_token.verify_oauth2_token(
                value, 
                requests.Request(), 
                settings.GOOGLE_CLIENT_ID
            )

            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise ValueError('Wrong issuer.')

            return idinfo
        except ValueError:
            raise serializers.ValidationError('Invalid token') 