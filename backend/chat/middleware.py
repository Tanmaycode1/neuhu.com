from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
import jwt
from django.conf import settings
import logging
from urllib.parse import parse_qs
import traceback
import json
import time
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)
User = get_user_model()

class WebSocketAuthError(Exception):
    def __init__(self, message: str, code: int = 4001):
        self.message = message
        self.code = code
        super().__init__(message)

class WebSocketJWTAuthMiddleware(BaseMiddleware):
    def __init__(self, inner):
        super().__init__(inner)
        self._auth_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_cleanup_threshold = 1000
        self._cache_ttl = 300  # 5 minutes
        self._last_cleanup = time.time()

    async def __call__(self, scope, receive, send):
        try:
            logger.info("Starting WebSocket authentication process")
            
            # Periodic cache cleanup
            await self._maybe_cleanup_cache()
            
            # Get and validate token
            token = await self._get_and_validate_token(scope)
            if not token:
                return await self._close_connection(send, "No valid authentication token provided", 4001)
            
            # Try to authenticate user
            try:
                user, auth_info = await self._authenticate_token(token)
                if not user:
                    return await self._close_connection(send, "Authentication failed", 4001)
            except WebSocketAuthError as e:
                return await self._close_connection(send, e.message, e.code)
            
            # Add user and auth info to scope
            scope.update({
                'user': user,
                'auth': {
                    'token': token,
                    'user_id': str(user.id),
                    'authenticated_at': time.time(),
                    **auth_info
                }
            })
            
            logger.info(f"WebSocket authenticated for user: {user.id}")
            return await super().__call__(scope, receive, send)
            
        except Exception as e:
            logger.error(f"WebSocket authentication error: {str(e)}")
            logger.error(traceback.format_exc())
            return await self._close_connection(send, "Internal server error", 4500)

    async def _get_and_validate_token(self, scope) -> Optional[str]:
        """Get and perform basic validation of the token."""
        try:
            token = self._get_token_from_scope(scope)
            if not token:
                return None

            # Basic token format validation
            parts = token.split('.')
            if len(parts) != 3:
                raise WebSocketAuthError("Invalid token format", 4001)

            return token
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}")
            return None

    def _get_token_from_scope(self, scope) -> Optional[str]:
        """Extract token from scope's query string."""
        try:
            query_string = scope.get("query_string", b"").decode()
            query_params = parse_qs(query_string)
            token = query_params.get('token', [None])[0]
            
            if not token:
                logger.error("No token provided in query string")
                return None
                
            return token
        except Exception as e:
            logger.error(f"Error extracting token: {str(e)}")
            return None

    async def _authenticate_token(self, token: str) -> Tuple[Optional[User], Dict[str, Any]]:
        """Authenticate token and return user if valid."""
        try:
            # Check cache first
            if len(token) < 32:
                raise WebSocketAuthError("Invalid token length", 4001)
                
            cache_key = f"ws_auth_{token[-32:]}"
            cached_auth = self._auth_cache.get(cache_key)
            
            if cached_auth:
                # Verify cache hasn't expired
                if time.time() - cached_auth['timestamp'] > self._cache_ttl:
                    self._auth_cache.pop(cache_key, None)
                else:
                    return cached_auth['user'], cached_auth['auth_info']

            # Verify and decode token
            try:
                payload = jwt.decode(
                    token,
                    settings.SECRET_KEY,
                    algorithms=["HS256", "RS256"],
                    options={
                        'verify_exp': True,
                        'verify_iat': True,
                        'require': ['exp', 'iat', 'user_id']
                    }
                )
            except jwt.ExpiredSignatureError:
                raise WebSocketAuthError("Token has expired", 4001)
            except jwt.InvalidTokenError as e:
                raise WebSocketAuthError(f"Invalid token: {str(e)}", 4001)

            # Validate token claims
            if not self._validate_token_claims(payload):
                raise WebSocketAuthError("Invalid token claims", 4001)

            # Get user from database
            user = await self.get_user(payload)
            if not user:
                raise WebSocketAuthError("User not found", 4001)

            # Create auth info
            auth_info = {
                'exp': payload.get('exp'),
                'iat': payload.get('iat'),
                'scopes': payload.get('scopes', []),
                'token_type': payload.get('token_type', 'access')
            }

            # Update cache
            self._update_auth_cache(cache_key, user, auth_info)
            return user, auth_info

        except WebSocketAuthError:
            raise
        except Exception as e:
            logger.error(f"Token authentication error: {str(e)}")
            return None, {}

    def _validate_token_claims(self, payload: Dict[str, Any]) -> bool:
        """Validate the token claims."""
        try:
            now = datetime.utcnow().timestamp()
            
            # Check expiration
            exp = payload.get('exp', 0)
            if exp < now:
                return False
                
            # Check issued at
            iat = payload.get('iat', 0)
            if iat > now:
                return False
                
            # Check required fields
            required_fields = ['user_id', 'exp', 'iat']
            if not all(field in payload for field in required_fields):
                return False
                
            return True
        except Exception as e:
            logger.error(f"Token claims validation error: {str(e)}")
            return False

    def _update_auth_cache(self, cache_key: str, user: User, auth_info: Dict[str, Any]):
        """Update the authentication cache."""
        self._auth_cache[cache_key] = {
            'user': user,
            'auth_info': auth_info,
            'timestamp': time.time()
        }

        # Clean cache if it's too large
        if len(self._auth_cache) > self._cache_cleanup_threshold:
            self._cleanup_auth_cache()

    def _cleanup_auth_cache(self):
        """Remove expired entries from auth cache."""
        current_time = time.time()
        self._auth_cache = {
            k: v for k, v in self._auth_cache.items()
            if current_time - v['timestamp'] < self._cache_ttl
        }
        self._last_cleanup = current_time

    async def _maybe_cleanup_cache(self):
        """Perform cache cleanup if needed."""
        if time.time() - self._last_cleanup > 300:  # Cleanup every 5 minutes
            self._cleanup_auth_cache()

    @database_sync_to_async
    def get_user(self, payload: Dict[str, Any]) -> Optional[User]:
        """Get user from database."""
        try:
            user_id = payload.get('user_id')
            if not user_id:
                return None

            user = User.objects.get(id=user_id)
            
            # Check if user is active
            if not user.is_active:
                raise WebSocketAuthError("User account is disabled", 4001)
                
            return user
        except User.DoesNotExist:
            logger.warning(f"User not found for ID: {payload.get('user_id')}")
            return None
        except Exception as e:
            logger.error(f"Error getting user: {str(e)}")
            return None

    async def _close_connection(self, send, message: str, code: int = 4000):
        """Close WebSocket connection with error message."""
        try:
            await send({
                "type": "websocket.close",
                "code": code,
                "text": json.dumps({
                    "error": message,
                    "code": code,
                    "timestamp": int(time.time())
                })
            })
        except Exception as e:
            logger.error(f"Error closing connection: {str(e)}")