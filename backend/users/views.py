from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import User, UserProfile
from .serializers import UserSerializer, UserCreateSerializer, UserProfileSerializer
from core.decorators import handle_exceptions, paginate_response
from core.utils.response import api_response, error_response, ErrorCode
from rest_framework.decorators import api_view, permission_classes, parser_classes, authentication_classes
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from PIL import Image
from io import BytesIO
import logging
from rest_framework.authentication import BasicAuthentication

logger = logging.getLogger(__name__)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ['send_verification_otp', 'verify_email_otp']:
            return [AllowAny()]
        return super().get_permissions()

    @handle_exceptions
    @paginate_response
    def list(self, request, *args, **kwargs):
        """Get list of all users"""
        return self.get_queryset()

    @handle_exceptions
    def create(self, request, *args, **kwargs):
        """Create a new user"""
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check if email is verified
        email = request.data.get('email')
        if not User.objects.filter(email=email, email_verified=True).exists():
            return api_response(
                success=False,
                message="Email must be verified before registration",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        user = serializer.save()
        return api_response(
            message="User created successfully",
            data=self.get_serializer(user).data,
            status_code=status.HTTP_201_CREATED
        )

    @handle_exceptions
    def retrieve(self, request, pk=None):
        """Get user details by ID"""
        user = self.get_object()
        serializer = self.get_serializer(user)
        return api_response(
            message="User details retrieved successfully",
            data=serializer.data
        )

    @handle_exceptions
    def update(self, request, pk=None):
        """Update user details"""
        user = self.get_object()
        serializer = self.get_serializer(user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return api_response(
            message="User updated successfully",
            data=serializer.data
        )

    @handle_exceptions
    def partial_update(self, request, pk=None):
        """Partial update user details"""
        user = self.get_object()
        serializer = self.get_serializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return api_response(
            message="User partially updated successfully",
            data=serializer.data
        )

    @handle_exceptions
    def destroy(self, request, pk=None):
        """Delete user"""
        user = self.get_object()
        user.delete()
        return api_response(
            message="User deleted successfully"
        )

    @handle_exceptions
    @action(detail=True, methods=['POST'])
    def follow(self, request, pk=None):
        """Follow a user"""
        user_to_follow = self.get_object()
        if user_to_follow == request.user:
            return api_response(
                success=False,
                message="You cannot follow yourself",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        request.user.following.add(user_to_follow)
        request.user.profile.update_counts()
        user_to_follow.profile.update_counts()
        
        return api_response(
            message=f"Now following {user_to_follow.username}",
            data={'user_id': str(user_to_follow.id)}
        )

    @handle_exceptions
    @action(detail=True, methods=['POST'])
    def unfollow(self, request, pk=None):
        """Unfollow a user"""
        user_to_unfollow = self.get_object()
        request.user.following.remove(user_to_unfollow)
        request.user.profile.update_counts()
        user_to_unfollow.profile.update_counts()
        
        return api_response(
            message=f"Unfollowed {user_to_unfollow.username}",
            data={'user_id': str(user_to_unfollow.id)}
        )

    @handle_exceptions
    @paginate_response
    @action(detail=False, methods=['GET'])
    def followers(self, request):
        """Get list of followers"""
        return User.objects.filter(following=request.user)

    @handle_exceptions
    @paginate_response
    @action(detail=False, methods=['GET'])
    def following(self, request):
        """Get list of users being followed"""
        return request.user.following.all()

    @handle_exceptions
    @action(detail=False, methods=['GET'])
    def me(self, request):
        """Get own profile details"""
        return api_response(
            message="Profile retrieved successfully",
            data=self.get_serializer(request.user).data
        )

    @handle_exceptions
    @action(detail=False, methods=['PUT', 'PATCH'])
    def update_profile(self, request):
        """Update profile details"""
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return api_response(
            message="Profile updated successfully",
            data=serializer.data
        )

    @handle_exceptions
    @action(detail=False, methods=['GET'])
    def search(self, request):
        """Search users by username or email"""
        query = request.query_params.get('q', '')
        if not query:
            return api_response(
                success=False,
                message="Search query is required",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        users = User.objects.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )
        serializer = self.get_serializer(users, many=True)
        return api_response(
            message="Search results",
            data=serializer.data
        )

    @handle_exceptions
    @action(detail=False, methods=['GET'])
    def suggestions(self, request):
        """Get user suggestions (users not being followed)"""
        following_ids = request.user.following.values_list('id', flat=True)
        suggestions = User.objects.exclude(
            id__in=list(following_ids) + [request.user.id]
        )[:10]  # Limit to 10 suggestions
        serializer = self.get_serializer(suggestions, many=True)
        return api_response(
            message="User suggestions retrieved",
            data=serializer.data
        )

@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def send_verification_otp(request):
    """Send email verification OTP"""
    email = request.data.get('email')
    if not email:
        return Response({
            'success': False,
            'message': "Email is required"
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Create temporary user if doesn't exist
        user, _ = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email.split('@')[0],
                'is_active': False
            }
        )
        
        if user.generate_and_send_otp():
            return Response({
                'success': True,
                'message': "OTP sent successfully"
            })
        return Response({
            'success': False,
            'message': "Failed to send OTP"
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def verify_email_otp(request):
    """Verify email with OTP"""
    email = request.data.get('email')
    otp = request.data.get('otp')

    if not email or not otp:
        return Response({
            'success': False,
            'message': "Email and OTP are required"
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(email=email)
        if user.verify_email_with_otp(otp):
            # Mark email as verified
            user.email_verified = True
            user.save()
            return Response({
                'success': True,
                'message': "Email verified successfully"
            })
        return Response({
            'success': False,
            'message': "Invalid or expired OTP"
        }, status=status.HTTP_400_BAD_REQUEST)
    except User.DoesNotExist:
        return Response({
            'success': False,
            'message': "User not found"
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def check_email(request, email):
    """Check if email exists and is verified"""
    try:
        user = User.objects.get(email=email)
        return Response({
            'success': True,
            'email_verified': user.email_verified
        })
    except User.DoesNotExist:
        return Response({
            'success': False,
            'message': "User not found"
        }, status=status.HTTP_404_NOT_FOUND)        

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def update_avatar(request):
    """Update user's avatar"""
    try:
        avatar = request.FILES.get('avatar')
        if not avatar:
            return error_response(
                "No image file provided", 
                ErrorCode.REQUIRED_FIELD
            )

        # Validate file type
        if not avatar.content_type.startswith('image/'):
            return error_response(
                "Invalid file type. Please upload an image", 
                ErrorCode.INVALID_IMAGE
            )

        # Validate file size (5MB max)
        if avatar.size > 5 * 1024 * 1024:
            return error_response(
                "File size too large. Maximum size is 5MB", 
                ErrorCode.FILE_TOO_LARGE
            )

        # Process and optimize the image
        try:
            img = Image.open(avatar)
            
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize if too large (max 1000x1000)
            if img.height > 1000 or img.width > 1000:
                output_size = (1000, 1000)
                img.thumbnail(output_size)
            
            # Save to BytesIO
            img_io = BytesIO()
            img.save(img_io, format='JPEG', quality=85)
            
            # Generate unique filename
            file_name = f"avatars/{request.user.id}/{avatar.name}"
            
            # Delete old avatar if exists
            if request.user.avatar:
                default_storage.delete(request.user.avatar.name)
            
            # Save new avatar
            request.user.avatar = default_storage.save(
                file_name, 
                ContentFile(img_io.getvalue())
            )
            request.user.save()
            
            return Response({
                'success': True,
                'data': {
                    'avatar_url': request.user.avatar.url if request.user.avatar else None
                }
            })
            
        except Exception as e:
            return error_response(
                "Error processing image", 
                ErrorCode.INVALID_IMAGE
            )
            
    except Exception as e:
        return error_response(
            str(e), 
            ErrorCode.UNKNOWN_ERROR, 
            status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_profile(request):
    """Get user's profile"""
    serializer = UserProfileSerializer(request.user)
    return Response({
        'success': True,
        'data': serializer.data
    })

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """Update user's profile"""
    allowed_fields = [
        'first_name',
        'last_name',
        'bio',
        'social_links',
        'account_privacy'
    ]

    filtered_data = {
        k: v for k, v in request.data.items() 
        if k in allowed_fields
    }

    serializer = UserProfileSerializer(
        request.user, 
        data=filtered_data, 
        partial=True
    )
    
    if serializer.is_valid():
        serializer.save()
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    return error_response(
        "Invalid data provided", 
        ErrorCode.INVALID_FORMAT, 
        errors=serializer.errors
    )        