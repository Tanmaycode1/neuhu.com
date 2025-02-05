from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from urllib.parse import parse_qs
import jwt
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

class WebSocketJWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        try:
            # Get query string from scope
            query_string = scope.get('query_string', b'').decode()
            query_params = parse_qs(query_string)
            
            # Get token from query params
            token = query_params.get('token', [None])[0]
            
            if not token:
                logger.warning("No token provided for WebSocket connection")
                scope['user'] = AnonymousUser()
                return await super().__call__(scope, receive, send)

            try:
                # Verify the token
                decoded_token = jwt.decode(
                    token,
                    settings.SECRET_KEY,
                    algorithms=["HS256"]
                )
                user = await self.get_user(decoded_token)
                if not user or isinstance(user, AnonymousUser):
                    logger.warning("Invalid user from token")
                    scope['user'] = AnonymousUser()
                else:
                    scope['user'] = user
                    logger.info(f"WebSocket authenticated for user: {user.id}")
            except jwt.InvalidTokenError as e:
                logger.error(f"Invalid token: {str(e)}")
                scope['user'] = AnonymousUser()
            except Exception as e:
                logger.error(f"Token verification error: {str(e)}")
                scope['user'] = AnonymousUser()
            
            return await super().__call__(scope, receive, send)
        except Exception as e:
            logger.error(f"WebSocket middleware error: {str(e)}")
            scope['user'] = AnonymousUser()
            return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user(self, validated_token):
        try:
            user_id = validated_token.get('user_id')
            if not user_id:
                logger.error("No user_id in token")
                return AnonymousUser()
            
            user = User.objects.get(id=user_id)
            return user
        except User.DoesNotExist:
            logger.error(f"User not found: {user_id}")
            return AnonymousUser()
        except Exception as e:
            logger.error(f"Error getting user from token: {str(e)}")
            return AnonymousUser()