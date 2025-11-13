"""Redis cache configuration and utilities."""
import json
import logging
from typing import Any, Optional
from functools import wraps

import redis
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize Redis client
try:
    redis_client = redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    # Test connection
    redis_client.ping()
    logger.info("Redis connection established")
except (redis.ConnectionError, redis.TimeoutError) as e:
    logger.warning(f"Redis connection failed: {e}. Caching will be disabled.")
    redis_client = None


def get_cache_key(prefix: str, **kwargs) -> str:
    """Generate a cache key from prefix and kwargs."""
    key_parts = [prefix]
    for k, v in sorted(kwargs.items()):
        if v is not None:
            key_parts.append(f"{k}:{v}")
    return ":".join(key_parts)


def cache_result(expire: int = 3600, key_prefix: str = "cache"):
    """Decorator to cache function results in Redis.

    Args:
        expire: Cache expiration time in seconds (default: 1 hour)
        key_prefix: Prefix for cache keys
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if redis_client is None:
                # If Redis is not available, just call the function
                return func(*args, **kwargs)

            # Generate cache key
            # For instance methods, skip 'self' (first arg)
            # Exclude 'db' from kwargs as it's a session object
            cache_kwargs = {}
            
            # Handle positional arguments (skip self for instance methods)
            if args:
                # Check if this is an instance method (first arg has 'db' attribute)
                if len(args) > 0 and hasattr(args[0], 'db'):
                    # Instance method - skip self, use remaining args
                    if len(args) > 1:
                        # Convert args to kwargs for cache key
                        import inspect
                        sig = inspect.signature(func)
                        param_names = list(sig.parameters.keys())[1:]  # Skip 'self'
                        for i, arg in enumerate(args[1:], 0):
                            if i < len(param_names):
                                param_name = param_names[i]
                                if param_name != 'db':  # Skip db session
                                    cache_kwargs[param_name] = arg
                else:
                    # Regular function - include all args
                    import inspect
                    sig = inspect.signature(func)
                    param_names = list(sig.parameters.keys())
                    for i, arg in enumerate(args):
                        if i < len(param_names):
                            param_name = param_names[i]
                            if param_name != 'db':
                                cache_kwargs[param_name] = arg
            
            # Add kwargs (excluding 'db')
            for k, v in kwargs.items():
                if k != 'db':
                    cache_kwargs[k] = v
            
            cache_key = get_cache_key(key_prefix, func_name=func.__name__, **cache_kwargs)

            try:
                # Try to get from cache
                cached_value = redis_client.get(cache_key)
                if cached_value is not None:
                    logger.debug(f"Cache hit: {cache_key}")
                    return json.loads(cached_value)

                # Call the function
                result = func(*args, **kwargs)

                # Store in cache
                redis_client.setex(
                    cache_key,
                    expire,
                    json.dumps(result, default=str)
                )
                logger.debug(f"Cache set: {cache_key}")

                return result
            except Exception as e:
                logger.warning(f"Cache error for {cache_key}: {e}")
                # If caching fails, just call the function
                return func(*args, **kwargs)

        return wrapper
    return decorator


def get_from_cache(key: str) -> Optional[Any]:
    """Get a value from cache."""
    if redis_client is None:
        return None
    try:
        value = redis_client.get(key)
        if value is not None:
            return json.loads(value)
        return None
    except Exception as e:
        logger.warning(f"Cache get error for {key}: {e}")
        return None


def set_in_cache(key: str, value: Any, expire: int = 3600) -> bool:
    """Set a value in cache."""
    if redis_client is None:
        return False
    try:
        redis_client.setex(key, expire, json.dumps(value, default=str))
        return True
    except Exception as e:
        logger.warning(f"Cache set error for {key}: {e}")
        return False


def delete_from_cache(key: str) -> bool:
    """Delete a value from cache."""
    if redis_client is None:
        return False
    try:
        redis_client.delete(key)
        return True
    except Exception as e:
        logger.warning(f"Cache delete error for {key}: {e}")
        return False


def clear_cache_pattern(pattern: str) -> int:
    """Clear all cache keys matching a pattern."""
    if redis_client is None:
        return 0
    try:
        keys = redis_client.keys(pattern)
        if keys:
            return redis_client.delete(*keys)
        return 0
    except Exception as e:
        logger.warning(f"Cache clear error for pattern {pattern}: {e}")
        return 0

