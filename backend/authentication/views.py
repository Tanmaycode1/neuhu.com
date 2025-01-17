from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated  # Added IsAuthenticated here
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from django.contrib.auth import authenticate
from django.core.exceptions import ObjectDoesNotExist
from .serializers import RegisterSerializer, LoginSerializer, GoogleAuthSerializer
from users.models import User
from rest_framework.decorators import api_view, permission_classes, authentication_classes

##aa

class RegisterView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                # Check if user exists and is verified
                user = User.objects.get(email=email)
                if not user.email_verified:
                    return Response({
                        'success': False,
                        'message': 'Email must be verified before registration'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Update existing user
                user.set_password(serializer.validated_data['password'])
                user.username = serializer.validated_data['username']
                user.first_name = serializer.validated_data.get('first_name', '')
                user.last_name = serializer.validated_data.get('last_name', '')
                user.is_active = True
                user.save()
            except User.DoesNotExist:
                # Create new user if doesn't exist
                user = serializer.save()
                user.is_active = True
                user.save()

            # Generate tokens
            refresh = RefreshToken.for_user(user)
            return Response({
                'success': True,
                'data': {
                    'user': {
                        'id': str(user.id),
                        'email': user.email,
                        'username': user.username,
                        'first_name': user.first_name,
                        'last_name': user.last_name
                    },
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                }
            }, status=status.HTTP_201_CREATED)

        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']
            
            try:
                user = User.objects.get(email=email)
                authenticated_user = authenticate(
                    request,
                    email=email,
                    password=password
                )
                
                if authenticated_user is None:
                    return Response({
                        'success': False,
                        'message': 'Invalid credentials'
                    }, status=status.HTTP_401_UNAUTHORIZED)

                if not authenticated_user.email_verified:
                    authenticated_user.generate_and_send_otp()
                    return Response({
                        'success': False,
                        'message': 'Email not verified. Verification code sent.'
                    }, status=status.HTTP_403_FORBIDDEN)
                
                refresh = RefreshToken.for_user(authenticated_user)
                return Response({
                    'success': True,
                    'data': {
                        'tokens': {
                            'refresh': str(refresh),
                            'access': str(refresh.access_token),
                        },
                        'user': {
                            'id': authenticated_user.id,
                            'email': authenticated_user.email,
                            'username': authenticated_user.username
                        }
                    }
                })
                
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'User not found'
                }, status=status.HTTP_404_NOT_FOUND)
                
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        if serializer.is_valid():
            idinfo = serializer.validated_data['token']
            
            email = idinfo['email']
            name = idinfo.get('name', '')
            
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                user = User.objects.create(
                    email=email,
                    username=email.split('@')[0],
                    first_name=name.split()[0] if name else '',
                    last_name=name.split()[1] if name and len(name.split()) > 1 else '',
                    is_active=True,
                    email_verified=True  # Google OAuth emails are pre-verified
                )

            refresh = RefreshToken.for_user(user)
            return Response({
                'success': True,
                'data': {
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                }
            })
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)



class TestAuthView(APIView):
    """Test endpoint to verify if user is authenticated"""
    def get(self, request):
        return Response({
            'success': True,
            'message': 'You are authenticated',
            'user': request.user.email
        })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """Logout a user"""
    try:
        refresh_token = request.data.get('refresh_token')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({
                'success': True,
                'message': 'Successfully logged out'
            })
        else:
            return Response({
                'success': False,
                'message': 'Refresh token is required'
            }, status=status.HTTP_400_BAD_REQUEST)
    except TokenError:
        return Response({
            'success': False,
            'message': 'Invalid or expired token'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': 'Logout failed'
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def register(request):
    """Register a new user"""
    email = request.data.get('email')
    password = request.data.get('password')
    username = request.data.get('username')
    first_name = request.data.get('first_name', '')
    last_name = request.data.get('last_name', '')

    # Validate required fields
    if not all([email, password, username]):
        return Response({
            'success': False,
            'message': 'Email, password and username are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Check if email is verified
        user = User.objects.get(email=email)
        if not user.email_verified:
            return Response({
                'success': False,
                'message': 'Email must be verified before registration'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Update existing user (from OTP verification)
        user.set_password(password)
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.is_active = True
        user.save()

        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'success': True,
            'data': {
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                },
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                }
            }
        })
    except User.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Email not found or not verified'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def login(request):
    """Login a user"""
    email = request.data.get('email')
    password = request.data.get('password')

    # Validate required fields
    if not all([email, password]):
        return Response({
            'success': False,
            'message': 'Email and password are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Check if user exists
        user = User.objects.get(email=email)
        if not user.email_verified:
            return Response({
                'success': False,
                'message': 'Email not verified'
            }, status=status.HTTP_403_FORBIDDEN)

        # Authenticate user
        authenticated_user = authenticate(
            request,
            email=email,
            password=password
        )
        if authenticated_user is None:
            return Response({
                'success': False,
                'message': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)

        # Generate tokens
        refresh = RefreshToken.for_user(authenticated_user)
        return Response({
            'success': True,
            'data': {
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                },
                'user': {
                    'id': authenticated_user.id,
                    'email': authenticated_user.email,
                    'username': authenticated_user.username
                }
            }
        })
    except User.DoesNotExist:
        return Response({
            'success': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)