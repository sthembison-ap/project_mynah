"""
Session Store - Manages conversation state persistence.

This module provides session state storage for multi-turn conversations,
allowing context to be preserved across multiple API requests.

Supports:
- Redis backend (recommended for production)
- In-memory backend (for development/testing)
"""

from __future__ import annotations

import os
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from abc import ABC, abstractmethod

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class BaseSessionStore(ABC):
    """Abstract base class for session storage backends."""

    @abstractmethod
    def save_context(self, session_id: str, context_data: Dict[str, Any]) -> bool:
        """Save context data for a session."""
        pass

    @abstractmethod
    def load_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load context data for a session."""
        pass

    @abstractmethod
    def delete_context(self, session_id: str) -> bool:
        """Delete context data for a session."""
        pass

    @abstractmethod
    def exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        pass


class InMemorySessionStore(BaseSessionStore):
    """
    In-memory session store for development and testing.
    
    WARNING: Data is lost when the application restarts.
    Use Redis for production deployments.
    """

    def __init__(self, ttl_seconds: int = 3600):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._timestamps: Dict[str, datetime] = {}
        self.ttl = timedelta(seconds=ttl_seconds)

    def _is_expired(self, session_id: str) -> bool:
        """Check if a session has expired."""
        if session_id not in self._timestamps:
            return True
        return datetime.now() - self._timestamps[session_id] > self.ttl

    def _cleanup_expired(self) -> None:
        """Remove expired sessions."""
        expired = [
            sid for sid in self._timestamps
            if self._is_expired(sid)
        ]
        for sid in expired:
            self._store.pop(sid, None)
            self._timestamps.pop(sid, None)

    def save_context(self, session_id: str, context_data: Dict[str, Any]) -> bool:
        """Save context data for a session."""
        try:
            self._cleanup_expired()
            self._store[session_id] = context_data
            self._timestamps[session_id] = datetime.now()
            logger.debug(f"Saved context for session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save context for session {session_id}: {e}")
            return False

    def load_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load context data for a session."""
        try:
            if self._is_expired(session_id):
                self.delete_context(session_id)
                return None

            context = self._store.get(session_id)
            if context:
                # Update timestamp on access (sliding expiration)
                self._timestamps[session_id] = datetime.now()
                logger.debug(f"Loaded context for session: {session_id}")
            return context
        except Exception as e:
            logger.error(f"Failed to load context for session {session_id}: {e}")
            return None

    def delete_context(self, session_id: str) -> bool:
        """Delete context data for a session."""
        try:
            self._store.pop(session_id, None)
            self._timestamps.pop(session_id, None)
            logger.debug(f"Deleted context for session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete context for session {session_id}: {e}")
            return False

    def exists(self, session_id: str) -> bool:
        """Check if a session exists and is not expired."""
        if session_id not in self._store:
            return False
        if self._is_expired(session_id):
            self.delete_context(session_id)
            return False
        return True


class RedisSessionStore(BaseSessionStore):
    """
    Redis-backed session store for production use.
    
    Provides:
    - Persistent storage across restarts
    - Automatic TTL-based expiration
    - Scalability for multiple server instances
    """

    def __init__(self, ttl_seconds: int = 3600):
        self.ttl = ttl_seconds
        self._redis = None
        self._connect()

    def _connect(self) -> None:
        """Establish Redis connection."""
        try:
            import redis

            host = os.getenv("REDIS_HOST", "localhost")
            port = int(os.getenv("REDIS_PORT", "6379"))
            db = int(os.getenv("REDIS_DB", "0"))
            password = os.getenv("REDIS_PASSWORD", None)

            self._redis = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True
            )
            # Test connection
            self._redis.ping()
            logger.info(f"Connected to Redis at {host}:{port}")
        except ImportError:
            logger.warning("Redis package not installed. Install with: pip install redis")
            self._redis = None
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Falling back to in-memory store.")
            self._redis = None

    def _get_key(self, session_id: str) -> str:
        """Generate Redis key for a session."""
        return f"mynah:session:{session_id}"

    def save_context(self, session_id: str, context_data: Dict[str, Any]) -> bool:
        """Save context data for a session."""
        if not self._redis:
            return False

        try:
            key = self._get_key(session_id)
            self._redis.setex(
                key,
                self.ttl,
                json.dumps(context_data, default=str)
            )
            logger.debug(f"Saved context to Redis for session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save context to Redis for session {session_id}: {e}")
            return False

    def load_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load context data for a session."""
        if not self._redis:
            return None

        try:
            key = self._get_key(session_id)
            data = self._redis.get(key)

            if data:
                # Refresh TTL on access (sliding expiration)
                self._redis.expire(key, self.ttl)
                logger.debug(f"Loaded context from Redis for session: {session_id}")
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to load context from Redis for session {session_id}: {e}")
            return None

    def delete_context(self, session_id: str) -> bool:
        """Delete context data for a session."""
        if not self._redis:
            return False

        try:
            key = self._get_key(session_id)
            self._redis.delete(key)
            logger.debug(f"Deleted context from Redis for session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete context from Redis for session {session_id}: {e}")
            return False

    def exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        if not self._redis:
            return False

        try:
            key = self._get_key(session_id)
            return self._redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Failed to check session existence in Redis for {session_id}: {e}")
            return False


class SessionStore:
    """
    Main session store interface with automatic backend selection.
    
    Attempts to use Redis if available, falls back to in-memory storage.
    
    Usage:
        store = SessionStore()
        
        # Save context
        store.save(session_id, context)
        
        # Load context  
        context = store.load(session_id)
        
        # Delete context
        store.delete(session_id)
    """

    def __init__(self, ttl_seconds: int = 3600, prefer_redis: bool = True):
        """
        Initialize session store.
        
        Args:
            ttl_seconds: Session timeout in seconds (default: 1 hour)
            prefer_redis: Try Redis first, fall back to in-memory if unavailable
        """
        self.ttl = ttl_seconds
        self._backend: BaseSessionStore

        if prefer_redis:
            redis_store = RedisSessionStore(ttl_seconds)
            if redis_store._redis:
                self._backend = redis_store
                logger.info("Using Redis session store")
            else:
                self._backend = InMemorySessionStore(ttl_seconds)
                logger.info("Using in-memory session store (Redis unavailable)")
        else:
            self._backend = InMemorySessionStore(ttl_seconds)
            logger.info("Using in-memory session store")

    @property
    def is_redis(self) -> bool:
        """Check if using Redis backend."""
        return isinstance(self._backend, RedisSessionStore) and self._backend._redis is not None

    @property
    def redis_client(self):
        """Get the raw Redis client (if available)."""
        if self.is_redis:
            return self._backend._redis
        return None

    def save(self, session_id: str, context: Any) -> bool:
        """
        Save conversation context for a session.
        
        Args:
            session_id: Unique session identifier
            context: ConversationContext object or dict
            
        Returns:
            True if saved successfully, False otherwise
        """
        # Convert Pydantic model to dict if necessary
        if hasattr(context, 'model_dump'):
            context_data = context.model_dump(mode='json')
        elif hasattr(context, 'dict'):
            context_data = context.dict()
        elif isinstance(context, dict):
            context_data = context
        else:
            logger.error(f"Cannot serialize context of type {type(context)}")
            return False

        return self._backend.save_context(session_id, context_data)

    def load(self, session_id: str, context_class: Optional[type] = None) -> Optional[Any]:
        """
        Load conversation context for a session.
        
        Args:
            session_id: Unique session identifier
            context_class: Optional Pydantic model class to deserialize into
            
        Returns:
            ConversationContext object, dict, or None if not found
        """
        data = self._backend.load_context(session_id)

        if data is None:
            return None

        if context_class and hasattr(context_class, 'model_validate'):
            try:
                return context_class.model_validate(data)
            except Exception as e:
                logger.error(f"Failed to deserialize context: {e}")
                return data

        return data

    def delete(self, session_id: str) -> bool:
        """
        Delete conversation context for a session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            True if deleted successfully, False otherwise
        """
        return self._backend.delete_context(session_id)

    def exists(self, session_id: str) -> bool:
        """
        Check if a session exists.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            True if session exists, False otherwise
        """
        return self._backend.exists(session_id)

    def get_ttl(self, session_id: str) -> int:
        """
        Get remaining TTL for a session in seconds.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            TTL in seconds, -1 if no expiry, -2 if key doesn't exist
        """
        if self.is_redis:
            key = f"mynah:session:{session_id}"
            return self.redis_client.ttl(key)
        else:
            # For in-memory, calculate remaining time
            backend = self._backend
            if session_id in backend._timestamps:
                elapsed = datetime.now() - backend._timestamps[session_id]
                remaining = backend.ttl.total_seconds() - elapsed.total_seconds()
                return max(0, int(remaining))
            return -2

    def list_sessions(self, search: Optional[str] = None) -> list:
        """
        List all active sessions with metadata.
        
        Args:
            search: Optional filter by session_id or debtor_id
            
        Returns:
            List of session metadata dictionaries
        """
        sessions = []

        if self.is_redis:
            # Redis backend
            pattern = "mynah:session:*"
            for key in self.redis_client.scan_iter(pattern):
                session_id = key.split(":")[-1]
                ttl = self.redis_client.ttl(key)
                data = self.load(session_id)

                if data:
                    session_info = {
                        "session_id": session_id,
                        "debtor_id": data.get("debtor_id", "unknown"),
                        "ttl_seconds": ttl,
                        "last_intent": data.get("intent", "unknown"),
                        "last_message": data.get("last_user_message", "")[:50],
                        "agent_path": data.get("agent_path", []),
                        "has_id_number": bool(data.get("id_number")),
                        "has_matter_details": data.get("matter_details") is not None,
                    }
                    sessions.append(session_info)
        else:
            # In-memory backend
            backend = self._backend
            for session_id, data in backend._store.items():
                if backend._is_expired(session_id):
                    continue

                elapsed = datetime.now() - backend._timestamps[session_id]
                ttl = max(0, int(backend.ttl.total_seconds() - elapsed.total_seconds()))

                session_info = {
                    "session_id": session_id,
                    "debtor_id": data.get("debtor_id", "unknown"),
                    "ttl_seconds": ttl,
                    "last_intent": data.get("intent", "unknown"),
                    "last_message": data.get("last_user_message", "")[:50] if data.get("last_user_message") else "",
                    "agent_path": data.get("agent_path", []),
                    "has_id_number": bool(data.get("id_number")),
                    "has_matter_details": data.get("matter_details") is not None,
                }
                sessions.append(session_info)

        # Apply search filter
        if search:
            search_lower = search.lower()
            sessions = [
                s for s in sessions
                if search_lower in s["session_id"].lower()
                   or search_lower in s.get("debtor_id", "").lower()
            ]

        # Sort by TTL descending (newest first)
        sessions.sort(key=lambda x: x["ttl_seconds"], reverse=True)

        return sessions

    def get_stats(self) -> Dict[str, Any]:
        """
        Get session store statistics.
        
        Returns:
            Dictionary with storage stats
        """
        if self.is_redis:
            try:
                info = self.redis_client.info()
                session_count = len(list(self.redis_client.scan_iter("mynah:session:*")))

                return {
                    "backend": "redis",
                    "connected": True,
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory_human": info.get("used_memory_human", "N/A"),
                    "uptime_seconds": info.get("uptime_in_seconds", 0),
                    "total_keys": self.redis_client.dbsize(),
                    "session_keys": session_count,
                    "redis_version": info.get("redis_version", "unknown"),
                }
            except Exception as e:
                return {
                    "backend": "redis",
                    "connected": False,
                    "error": str(e),
                }
        else:
            # In-memory stats
            backend = self._backend
            backend._cleanup_expired()

            return {
                "backend": "in-memory",
                "connected": True,
                "session_keys": len(backend._store),
                "ttl_seconds": int(backend.ttl.total_seconds()),
            }

    def clear_all_sessions(self) -> int:
        """
        Clear all sessions (dangerous operation).
        
        Returns:
            Number of sessions deleted
        """
        count = 0

        if self.is_redis:
            pattern = "mynah:session:*"
            keys = list(self.redis_client.scan_iter(pattern))
            if keys:
                count = self.redis_client.delete(*keys)
        else:
            backend = self._backend
            count = len(backend._store)
            backend._store.clear()
            backend._timestamps.clear()

        logger.warning(f"Cleared {count} sessions")
        return count
