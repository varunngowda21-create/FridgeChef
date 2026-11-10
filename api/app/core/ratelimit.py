import time
from collections import defaultdict
from threading import Lock

from fastapi import Request

from app.core.config import Settings, get_settings
from app.core.errors import AppError


class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding window rate limiter."""

    def __init__(
        self,
        limit: int = 10,
        window_seconds: int = 900,
        error_code: str = "RATE_LIMIT_EXCEEDED",
        error_message: str = "Too many attempts. Please try again later.",
    ):
        self.limit = limit
        self.window_seconds = window_seconds
        self.error_code = error_code
        self.error_message = error_message
        self._history: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check_and_record(self, key: str) -> None:
        """Record an attempt. Raises AppError if limit exceeded."""
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            # Filter timestamps outside the window
            timestamps = [t for t in self._history[key] if t > cutoff]
            if len(timestamps) >= self.limit:
                oldest_timestamp = timestamps[0]
                retry_after = max(1, int(oldest_timestamp + self.window_seconds - now))
                raise AppError(
                    code=self.error_code,
                    message=self.error_message,
                    status_code=429,
                    details={"retry_after_seconds": retry_after},
                    headers={"Retry-After": str(retry_after)},
                )
            timestamps.append(now)
            self._history[key] = timestamps

    def reset(self, key: str) -> None:
        """Clear attempts for a key (e.g. after successful login)."""
        with self._lock:
            if key in self._history:
                del self._history[key]

    def clear(self) -> None:
        """Clear all rate limit histories (useful for testing)."""
        with self._lock:
            self._history.clear()


# Global login rate limiter: 10 attempts per 15 minutes (900 seconds) per PRD NFR-023
login_rate_limiter = SlidingWindowRateLimiter(limit=10, window_seconds=900)

# Global scan rate limiter: 20 scans per day (86400 seconds) per PRD NFR-022, FR-020, Section 11.4
scan_rate_limiter = SlidingWindowRateLimiter(
    limit=20,
    window_seconds=86400,
    error_code="SCAN_LIMIT_REACHED",
    error_message="Daily scan limit reached. Please try again later.",
)

# Global recommendation rate limiter: 60 requests per hour (3600 seconds) per PRD NFR-022
recommendation_rate_limiter = SlidingWindowRateLimiter(
    limit=60,
    window_seconds=3600,
    error_code="RATE_LIMIT_EXCEEDED",
    error_message="Hourly recommendation limit reached. Please try again later.",
)

# Global general request rate limiter: 200 requests per minute (60 seconds) per PRD NFR-022
general_rate_limiter = SlidingWindowRateLimiter(
    limit=200,
    window_seconds=60,
    error_code="RATE_LIMIT_EXCEEDED",
    error_message="Rate limit exceeded. Maximum 200 requests per minute.",
)


def get_client_ip(request: Request, settings: Settings | None = None) -> str:
    """Extract client IP, trusting proxy headers (X-Forwarded-For, X-Real-IP) strictly

    if the direct connecting peer is a trusted reverse proxy per PRD Section 15.1/15.3.
    """
    if settings is None:
        settings = get_settings()

    peer_ip = request.client.host if request.client else "127.0.0.1"
    trusted = settings.trusted_proxies_list

    # Accept proxy headers ONLY if direct connection is from a trusted proxy or testclient
    from app.core.security import is_ip_trusted

    if is_ip_trusted(peer_ip, trusted):
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            hops = [h.strip() for h in forwarded.split(",") if h.strip()]
            if hops:
                return hops[0]
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

    return peer_ip


def get_client_identity(request: Request, settings: Settings | None = None) -> str:
    """Determine client identity for general rate limiting.

    - Authenticated users with a verified Bearer token are keyed as 'user:<user_id>' (per-user quota).
    - Unauthenticated, expired, or invalid tokens fall back to 'ip:<client_ip>' to prevent attackers
      from evading rate limits with spoofed/changing tokens.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        raw_token = auth_header[7:].strip()
        if raw_token:
            from app.core.security import decode_access_token

            try:
                payload = decode_access_token(raw_token)
                user_id = payload.get("sub")
                if user_id:
                    return f"user:{user_id}"
            except AppError:
                # Invalid, expired, or malformed token: fall back to IP to throttle attacker
                pass

    client_ip = get_client_ip(request, settings)
    return f"ip:{client_ip}"


