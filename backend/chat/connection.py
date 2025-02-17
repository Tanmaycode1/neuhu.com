from typing import Dict, Set, Optional, Any
import asyncio
import time
import logging
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class ConnectionInfo:
    user_id: str
    room_id: str
    connection_id: str
    created_at: float
    last_activity: float
    metadata: Dict[str, Any]

class GlobalConnectionManager:
    """Singleton manager for all WebSocket connections."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        self._room_connections: Dict[str, Set[str]] = defaultdict(set)
        self._user_connections: Dict[str, Set[str]] = defaultdict(set)
        self._connection_info: Dict[str, ConnectionInfo] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task = None
        self._active = True
        self._connection_limits = {
            'per_user': 5,      # Max connections per user
            'per_room': 100,    # Max connections per room
            'total': 1000       # Max total connections
        }
        
    async def start(self):
        """Start the connection manager."""
        if not self._cleanup_task:
            self._active = True
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Connection manager started")
            
    async def stop(self):
        """Stop the connection manager and cleanup."""
        self._active = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        
        # Clear all connections
        async with self._lock:
            self._room_connections.clear()
            self._user_connections.clear()
            self._connection_info.clear()
        logger.info("Connection manager stopped")
            
    async def _cleanup_loop(self):
        """Periodic cleanup of stale connections."""
        while self._active:
            try:
                await self._cleanup_stale_connections()
                await asyncio.sleep(300)  # Run every 5 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {str(e)}")
                await asyncio.sleep(60)  # Wait a bit before retrying
                
    async def _cleanup_stale_connections(self):
        """Remove stale connections."""
        current_time = time.time()
        stale_threshold = current_time - 300  # 5 minutes
        
        async with self._lock:
            # Find stale connections
            stale_connections = [
                conn_id for conn_id, info in self._connection_info.items()
                if info.last_activity < stale_threshold
            ]
            
            # Remove each stale connection
            for conn_id in stale_connections:
                await self.remove_connection(conn_id)
                logger.info(f"Removed stale connection: {conn_id}")
                
    async def can_add_connection(self, user_id: str, room_id: str) -> bool:
        """Check if a new connection can be added."""
        async with self._lock:
            # Check total connection limit
            if len(self._connection_info) >= self._connection_limits['total']:
                logger.warning("Total connection limit reached")
                return False
                
            # Check per-room limit
            if len(self._room_connections[room_id]) >= self._connection_limits['per_room']:
                logger.warning(f"Room connection limit reached for room {room_id}")
                return False
                
            # Check per-user limit
            if len(self._user_connections[user_id]) >= self._connection_limits['per_user']:
                logger.warning(f"User connection limit reached for user {user_id}")
                return False
                
            return True
                
    async def add_connection(self, user_id: str, room_id: str, connection_id: str, metadata: Dict[str, Any] = None) -> bool:
        """Add a new connection."""
        try:
            if not await self.can_add_connection(user_id, room_id):
                return False
                
            async with self._lock:
                # Add to room connections
                self._room_connections[room_id].add(connection_id)
                
                # Add to user connections
                self._user_connections[user_id].add(connection_id)
                
                # Store connection info
                self._connection_info[connection_id] = ConnectionInfo(
                    user_id=user_id,
                    room_id=room_id,
                    connection_id=connection_id,
                    created_at=time.time(),
                    last_activity=time.time(),
                    metadata=metadata or {}
                )
                
                logger.info(f"Added connection {connection_id} for user {user_id} in room {room_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error adding connection: {str(e)}")
            return False
            
    async def remove_connection(self, connection_id: str) -> bool:
        """Remove a connection."""
        try:
            async with self._lock:
                if connection_id in self._connection_info:
                    info = self._connection_info[connection_id]
                    
                    # Remove from room connections
                    self._room_connections[info.room_id].discard(connection_id)
                    if not self._room_connections[info.room_id]:
                        del self._room_connections[info.room_id]
                        
                    # Remove from user connections
                    self._user_connections[info.user_id].discard(connection_id)
                    if not self._user_connections[info.user_id]:
                        del self._user_connections[info.user_id]
                        
                    # Remove connection info
                    del self._connection_info[connection_id]
                    
                    logger.info(f"Removed connection {connection_id}")
                    return True
                    
                return False
                
        except Exception as e:
            logger.error(f"Error removing connection: {str(e)}")
            return False
                
    async def update_activity(self, connection_id: str) -> bool:
        """Update last activity time for a connection."""
        try:
            async with self._lock:
                if connection_id in self._connection_info:
                    self._connection_info[connection_id].last_activity = time.time()
                    return True
                return False
        except Exception as e:
            logger.error(f"Error updating activity: {str(e)}")
            return False
                
    async def get_room_connections(self, room_id: str) -> Set[str]:
        """Get all connection IDs for a room."""
        async with self._lock:
            return self._room_connections.get(room_id, set()).copy()
        
    async def get_user_connections(self, user_id: str) -> Set[str]:
        """Get all connection IDs for a user."""
        async with self._lock:
            return self._user_connections.get(user_id, set()).copy()
            
    async def get_connection_info(self, connection_id: str) -> Optional[ConnectionInfo]:
        """Get information about a specific connection."""
        async with self._lock:
            return self._connection_info.get(connection_id)
            
    async def get_room_user_count(self, room_id: str) -> int:
        """Get number of unique users in a room."""
        async with self._lock:
            if room_id not in self._room_connections:
                return 0
            user_ids = {
                self._connection_info[conn_id].user_id
                for conn_id in self._room_connections[room_id]
                if conn_id in self._connection_info
            }
            return len(user_ids)
            
    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get current connection statistics."""
        async with self._lock:
            return {
                'total_connections': len(self._connection_info),
                'total_rooms': len(self._room_connections),
                'total_users': len(self._user_connections),
                'room_stats': {
                    room_id: len(connections)
                    for room_id, connections in self._room_connections.items()
                },
                'user_stats': {
                    user_id: len(connections)
                    for user_id, connections in self._user_connections.items()
                }
            }
            
    def set_connection_limits(self, limits: Dict[str, int]):
        """Update connection limits."""
        self._connection_limits.update(limits)
        logger.info(f"Updated connection limits: {self._connection_limits}")

# Global instance
connection_manager = GlobalConnectionManager() 