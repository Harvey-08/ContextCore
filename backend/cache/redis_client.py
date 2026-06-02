import os
import json
import logging
from typing import Any, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("redis_cache")
logging.basicConfig(level=logging.INFO)

class RedisClient:
    """
    Singleton Redis client with robust fault tolerance.
    If Redis is not running or fails, all operations will fail gracefully
    without raising exceptions, acting as a cache-miss.
    """
    _instance = None
    _redis_conn = None
    _failed_logged = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RedisClient, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        # Prevent re-initialization if already initialized
        if self._redis_conn is not None:
            return
            
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", 6379))
        db = int(os.getenv("REDIS_DB", 0))
        
        try:
            import redis
            logger.info(f"Initializing Redis Connection Pool (Host: {host}, Port: {port}, DB: {db})...")
            pool = redis.ConnectionPool(
                host=host, 
                port=port, 
                db=db, 
                socket_timeout=2.0, 
                socket_connect_timeout=2.0,
                retry_on_timeout=True
            )
            self._redis_conn = redis.Redis(connection_pool=pool)
            # Test connection immediately
            self._redis_conn.ping()
            logger.info("[Redis Cache] Connected to Redis successfully!")
        except Exception as e:
            self._redis_conn = None
            if not self.__class__._failed_logged:
                logger.warning(
                    f"[Redis Cache Warning] Could not connect to Redis server: {e}. "
                    "All caching will be bypassed gracefully."
                )
                self.__class__._failed_logged = True

    @property
    def is_connected(self) -> bool:
        if self._redis_conn is None:
            return False
        try:
            self._redis_conn.ping()
            return True
        except Exception:
            return False

    def get(self, key: str) -> Optional[str]:
        """Get raw value from Redis by key."""
        if not self._redis_conn:
            return None
        try:
            val = self._redis_conn.get(key)
            if val is not None:
                return val.decode("utf-8")
        except Exception as e:
            logger.debug(f"Redis get error: {e}")
        return None

    def set(self, key: str, value: str, ex_seconds: Optional[int] = None) -> bool:
        """Set raw string value in Redis with optional TTL."""
        if not self._redis_conn:
            return False
        try:
            self._redis_conn.set(key, value, ex=ex_seconds)
            return True
        except Exception as e:
            logger.debug(f"Redis set error: {e}")
            return False

    def get_json(self, key: str) -> Optional[Any]:
        """Retrieve and deserialize a JSON object from Redis."""
        raw_val = self.get(key)
        if raw_val is None:
            return None
        try:
            return json.loads(raw_val)
        except Exception as e:
            logger.warning(f"Failed to decode cached JSON from key '{key}': {e}. Purging corrupted key from cache.")
            self.delete(key)
            return None

    def set_json(self, key: str, value: Any, ex_seconds: Optional[int] = None) -> bool:
        """Serialize and cache a JSON-compatible object in Redis."""
        try:
            serialized = json.dumps(value, ensure_ascii=False)
            return self.set(key, serialized, ex_seconds=ex_seconds)
        except Exception as e:
            logger.warning(f"Failed to encode JSON for key '{key}': {e}")
            return False

    def get_status(self, key: str) -> Optional[str]:
        """Helper to get text-only statuses (e.g. video job status)."""
        return self.get(key)

    def set_status(self, key: str, status: str, ex_seconds: Optional[int] = None) -> bool:
        """Helper to set text-only status with expiration."""
        return self.set(key, status, ex_seconds=ex_seconds)

    def delete(self, key: str) -> bool:
        """Remove a key from Redis."""
        if not self._redis_conn:
            return False
        try:
            self._redis_conn.delete(key)
            return True
        except Exception as e:
            logger.debug(f"Redis delete error: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if a key exists in Redis."""
        if not self._redis_conn:
            return False
        try:
            return bool(self._redis_conn.exists(key))
        except Exception as e:
            logger.debug(f"Redis exists error: {e}")
            return False


# Singleton Instance Expo
redis_client = RedisClient()
