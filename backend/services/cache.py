"""
Optional Redis-backed response cache and idempotency helper.
No-ops entirely when REDIS_URL isn't configured — the app must behave
identically with zero additional infrastructure.
"""

import json
import logging
from typing import Optional, Callable, Any
from functools import wraps
from inspect import iscoroutinefunction

from backend.config import settings

logger = logging.getLogger(__name__)
_redis = None


async def _get_redis():
    global _redis
    if _redis is None and getattr(settings, 'REDIS_URL', None):
        import redis.asyncio as redis
        _redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def get_cached(key: str) -> Optional[dict]:
    r = await _get_redis()
    if r is None:
        return None
    try:
        raw = await r.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as e:
        logger.warning(f"Cache read failed for {key}: {e}")
        return None


async def set_cached(key: str, value: dict, ttl_seconds: int = 30) -> None:
    r = await _get_redis()
    if r is None:
        return
    try:
        await r.set(key, json.dumps(value, default=str), ex=ttl_seconds)
    except Exception as e:
        logger.warning(f"Cache write failed for {key}: {e}")


async def delete_cached(key: str) -> None:
    r = await _get_redis()
    if r is None:
        return
    try:
        await r.delete(key)
    except Exception as e:
        logger.warning(f"Cache delete failed for {key}: {e}")


async def is_duplicate_webhook_delivery(message_sid: str) -> bool:
    """
    Idempotency guard for Twilio webhook retries: returns True only if
    this MessageSid has already been processed in the last 24h. Always
    returns False (never blocks) when Redis isn't configured.
    """
    if not message_sid:
        return False
    r = await _get_redis()
    if r is None:
        return False
    try:
        was_set = await r.set(f"twilio_msg:{message_sid}", "1", nx=True, ex=86400)
        return not bool(was_set)
    except Exception as e:
        logger.warning(f"Idempotency check failed for {message_sid}: {e}")
        return False


def cache_response(ttl: int = 3600, key_prefix: str = "cache"):
    """
    Decorator to cache the JSON response of FastAPI endpoints.
    Uses the request path and query string as the cache key suffix.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # We need to find the Request object to build the cache key
            # or rely on kwargs like household_id
            
            # Simple heuristic: look for household_id or user_id in kwargs
            suffix_parts = []
            if "household_id" in kwargs:
                suffix_parts.append(f"hh_{kwargs['household_id']}")
            elif "user_id" in kwargs:
                suffix_parts.append(f"usr_{kwargs['user_id']}")
                
            suffix = "_".join(suffix_parts) if suffix_parts else "global"
            cache_key = f"{key_prefix}:{suffix}"
            
            cached_val = await get_cached(cache_key)
            if cached_val is not None:
                return cached_val
                
            if iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
                
            if result is not None:
                await set_cached(cache_key, result, ttl)
                
            return result
        return wrapper
    return decorator
