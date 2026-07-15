import json
import hashlib
from loguru import logger
from upstash_redis import Redis
from app.core.config import settings


class CacheService:
    """
    Two responsibilities:
      1. Rate limiting  — sliding window counter per user in Redis
      2. Answer caching — store full RAG answers, return instantly on repeat questions
    """

    # How many requests a user can make per minute
    RATE_WINDOW_SECONDS = 60

    # How long to keep a cached answer (1 hour)
    CACHE_TTL_SECONDS = 3600

    def __init__(self):
        self.redis = Redis(
            url=settings.upstash_redis_rest_url,
            token=settings.upstash_redis_rest_token,
        )
        logger.info("CacheService ready — Upstash Redis connected")

    # ------------------------------------------------------------------ #
    # Rate limiting                                                        #
    # ------------------------------------------------------------------ #

    def check_rate_limit(self, user_id: str) -> tuple[bool, int]:
        """
        Increment the user's request counter for this minute window.

        Returns:
            (is_allowed, requests_remaining)

        How it works:
            - Key: "rate:{user_id}"
            - On first request in a window: set counter to 1, expire in 60s
            - On subsequent requests: increment counter
            - If counter exceeds limit: block the request
        """
        key = f"rate:{user_id}"
        limit = settings.rate_limit_per_minute

        try:
            # INCR returns the new value after incrementing.
            # If the key doesn't exist, Redis creates it at 0 then increments to 1.
            count = self.redis.incr(key)

            # Only set the expiry on the first request of a new window.
            # If we set it every time, the window would keep extending.
            if count == 1:
                self.redis.expire(key, self.RATE_WINDOW_SECONDS)

            remaining = max(0, limit - count)
            allowed   = count <= limit

            if not allowed:
                logger.warning(f"Rate limit exceeded for user {user_id} — count={count}")

            return allowed, remaining

        except Exception as e:
            # If Redis is down, fail open — don't block legitimate users
            # just because the cache is unavailable
            logger.warning(f"Rate limit check failed (Redis error): {e} — allowing request")
            return True, limit

    # ------------------------------------------------------------------ #
    # Answer caching                                                       #
    # ------------------------------------------------------------------ #

    def _make_cache_key(self, user_id: str, question: str) -> str:
        """
        Build a cache key from user_id + normalised question.

        We normalise the question (lowercase, stripped) before hashing
        so that "What is the refund policy?" and "what is the refund policy"
        hit the same cache entry.
        """
        normalised = question.lower().strip()
        fingerprint = hashlib.md5(
            f"{user_id}:{normalised}".encode()
        ).hexdigest()
        return f"rag_cache:{fingerprint}"

    def get_cached_answer(self, user_id: str, question: str) -> str | None:
        """
        Check if we already have an answer for this question.
        Returns the cached answer string, or None if not found.
        """
        key = self._make_cache_key(user_id, question)
        try:
            value = self.redis.get(key)
            if value:
                logger.info(f"Cache HIT for user={user_id} question='{question[:40]}...'")
                return json.loads(value)
            logger.info(f"Cache MISS for user={user_id}")
            return None
        except Exception as e:
            logger.warning(f"Cache get failed: {e}")
            return None

    def set_cached_answer(self, user_id: str, question: str, answer: str) -> None:
        """
        Store the full answer in Redis with a TTL.
        Called after a successful RAG response completes streaming.
        """
        key = self._make_cache_key(user_id, question)
        try:
            self.redis.set(key, json.dumps(answer), ex=self.CACHE_TTL_SECONDS)
            logger.info(f"Cached answer for user={user_id} | TTL={self.CACHE_TTL_SECONDS}s")
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")

    def invalidate_user_cache(self, user_id: str) -> None:
        """
        Called when a user uploads or deletes a document.
        Their cached answers are now potentially stale, so we mark them invalid.

        Note: Upstash free tier doesn't support SCAN to find all keys by pattern,
        so we use a separate index key to track which cache keys belong to a user,
        then delete them individually.
        """
        index_key = f"rag_cache_index:{user_id}"
        try:
            raw = self.redis.get(index_key)
            if not raw:
                return

            cache_keys = json.loads(raw)
            if cache_keys:
                # Delete all cached answer keys for this user
                for key in cache_keys:
                    self.redis.delete(key)
                # Clear the index itself
                self.redis.delete(index_key)
                logger.info(f"Invalidated {len(cache_keys)} cached answers for user={user_id}")

        except Exception as e:
            logger.warning(f"Cache invalidation failed: {e} — answers will expire naturally via TTL")

    def _track_cache_key(self, user_id: str, cache_key: str) -> None:
        """
        Keep a list of cache keys per user so we can invalidate them all
        when their documents change.
        """
        index_key = f"rag_cache_index:{user_id}"
        try:
            raw = self.redis.get(index_key)
            keys = json.loads(raw) if raw else []
            if cache_key not in keys:
                keys.append(cache_key)
                # Index expires after 24h — after that, stale entries expire via TTL anyway
                self.redis.set(index_key, json.dumps(keys), ex=86400)
        except Exception as e:
            logger.warning(f"Cache key tracking failed: {e}")


# Single shared instance
cache_service = CacheService()