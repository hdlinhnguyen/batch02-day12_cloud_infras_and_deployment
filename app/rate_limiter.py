import time
import logging
from collections import defaultdict, deque
from fastapi import HTTPException
import redis
from app.config import settings

logger = logging.getLogger(__name__)

class RedisRateLimiter:
    def __init__(self, redis_client: redis.Redis | None = None, max_requests: int = 10, window_seconds: int = 60):
        self.r = redis_client
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # In-memory fallback
        self._memory_store = defaultdict(deque)

    def check(self, user_id: str):
        now = time.time()
        
        # Check if Redis is available
        if self.r is not None:
            try:
                key = f"rate_limit:{user_id}"
                # Use Redis Sorted Set for sliding window
                pipe = self.r.pipeline()
                # Remove timestamps older than window
                pipe.zremrangebyscore(key, 0, now - self.window_seconds)
                # Count current elements in window
                pipe.zcard(key)
                # Add current timestamp
                pipe.zadd(key, {str(now): now})
                # Set key expiry (window + buffer)
                pipe.expire(key, self.window_seconds + 5)
                # Run pipeline
                _, count, _, _ = pipe.execute()
                
                if count >= self.max_requests:
                    # Get oldest timestamp in window to estimate retry time
                    oldest = self.r.zrange(key, 0, 0, withscores=True)
                    retry_after = 1
                    if oldest:
                        retry_after = max(1, int(oldest[0][1] + self.window_seconds - now) + 1)
                    raise HTTPException(
                        status_code=429,
                        detail={
                            "error": "Rate limit exceeded",
                            "limit": self.max_requests,
                            "window_seconds": self.window_seconds,
                            "retry_after_seconds": retry_after,
                        }
                    )
                return {
                    "limit": self.max_requests,
                    "remaining": self.max_requests - count - 1,
                }
            except Exception as e:
                logger.warning(f"Redis rate limiting failed, falling back to memory: {e}")
                
        # In-memory fallback
        window = self._memory_store[user_id]
        while window and window[0] < now - self.window_seconds:
            window.popleft()
            
        if len(window) >= self.max_requests:
            oldest = window[0]
            retry_after = max(1, int(oldest + self.window_seconds - now) + 1)
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded (in-memory)",
                    "limit": self.max_requests,
                    "window_seconds": self.window_seconds,
                    "retry_after_seconds": retry_after,
                }
            )
        window.append(now)
        return {
            "limit": self.max_requests,
            "remaining": self.max_requests - len(window),
        }
