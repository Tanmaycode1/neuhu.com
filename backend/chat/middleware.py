from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
import jwt
from django.conf import settings
import logging
from urllib.parse import parse_qs
import traceback

logger = logging.getLogger(__name__)
User = get_user_model()

class WebSocketJWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        try:
            logger.info("Starting WebSocket authentication process")
            logger.info(f"Scope type: {scope.get('type')}")
            logger.info(f"Path: {scope.get('path')}")
            
            # Parse query string properly
            query_string = scope["query_string"].decode()
            logger.info(f"Raw query string: {query_string}")
            
            query_params = parse_qs(query_string)
            logger.info(f"Parsed query params: {query_params}")
            
            token = query_params.get('token', [None])[0]
            
            if not token:
                logger.error("No token provided in WebSocket connection")
                scope["user"] = AnonymousUser()
                return await self.close_connection(send, "No token provided")

            # Log the token for debugging (only in development)
            if settings.DEBUG:
                logger.debug(f"WebSocket auth token: {token[:20]}...")
                logger.debug(f"Secret key first 10 chars: {settings.SECRET_KEY[:10]}")

            logger.info("Attempting to decode JWT token")
            try:
                decoded = jwt.decode(
                    token, 
                    settings.SECRET_KEY, 
                    algorithms=["HS256"],
                    options={"verify_exp": True}
                )
                logger.info(f"Token decoded successfully. Full decoded token: {decoded}")
            except jwt.ExpiredSignatureError:
                logger.error("Token has expired")
                return await self.close_connection(send, "Token has expired")
            except jwt.InvalidTokenError as e:
                logger.error(f"Token decode failed: {str(e)}")
                return await self.close_connection(send, f"Invalid token: {str(e)}")
            
            try:
                user = await self.get_user(decoded)
                
                if user.is_anonymous:
                    error_msg = f"User not found for token user_id: {decoded.get('user_id')}"
                    logger.error(error_msg)
                    return await self.close_connection(send, error_msg)
                else:
                    logger.info(f"WebSocket authenticated for user: {user.id}")
                
                scope["user"] = user
                return await super().__call__(scope, receive, send)
            except Exception as e:
                logger.error(f"Error in user lookup: {str(e)}")
                logger.error(traceback.format_exc())
                return await self.close_connection(send, f"User lookup failed: {str(e)}")
            
        except Exception as e:
            logger.error(f"WebSocket auth error: {str(e)}")
            logger.error(traceback.format_exc())
            return await self.close_connection(send, f"Authentication failed: {str(e)}")

    async def close_connection(self, send, reason="Access denied"):
        """Helper method to close the connection with a 403 status"""
        logger.error(f"Closing connection: {reason}")
        await send({
            "type": "websocket.close",
            "code": 4003,  # Custom code for authentication failure
            "reason": reason
        })
        return None

    @database_sync_to_async
    def get_user(self, token_data):
        try:
            user_id = token_data.get("user_id")
            logger.info(f"Looking up user with ID: {user_id}")
            
            if not user_id:
                logger.error("No user_id in token data")
                return AnonymousUser()
            
            user = User.objects.get(id=user_id)
            logger.info(f"Found user: {user.email}")
            return user
        except User.DoesNotExist:
            logger.error(f"User with ID {token_data.get('user_id')} not found")
            return AnonymousUser()
        except Exception as e:
            logger.error(f"Error getting user: {str(e)}")
            logger.error(traceback.format_exc())
            return AnonymousUser()