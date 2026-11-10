"""Tests for rate limiting policies and security per PRD Section 7.3, NFR-022, NFR-023."""

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import AppError
from app.core.ratelimit import (
    SlidingWindowRateLimiter,
    general_rate_limiter,
    get_client_identity,
    get_client_ip,
    login_rate_limiter,
    recommendation_rate_limiter,
    scan_rate_limiter,
)
from app.core.security import create_access_token


def test_sliding_window_rate_limiter_unit():
    """Unit test for SlidingWindowRateLimiter logic, retry_after, and window expiration."""
    limiter = SlidingWindowRateLimiter(limit=3, window_seconds=10)
    key = "user_test_unit"

    # 3 attempts succeed
    limiter.check_and_record(key)
    limiter.check_and_record(key)
    limiter.check_and_record(key)

    # 4th attempt fails with 429, valid integer Retry-After, and structured details
    with pytest.raises(AppError) as exc_info:
        limiter.check_and_record(key)
    err = exc_info.value
    assert err.status_code == 429
    assert err.headers is not None
    assert "Retry-After" in err.headers
    retry_sec = int(err.headers["Retry-After"])
    assert 1 <= retry_sec <= 10
    assert err.details.get("retry_after_seconds") == retry_sec

    # Simulate time advance beyond window
    now = time.time()
    with patch("time.time", return_value=now + 11):
        # Should succeed again after window expiration
        limiter.check_and_record(key)


def test_specific_rate_limiters_configuration():
    """Verify configured limits and window durations for all PRD policies."""
    assert login_rate_limiter.limit == 10
    assert login_rate_limiter.window_seconds == 900  # 15 minutes (NFR-023)

    assert scan_rate_limiter.limit == 20
    assert scan_rate_limiter.window_seconds == 86400  # 24 hours (NFR-022)

    assert recommendation_rate_limiter.limit == 60
    assert recommendation_rate_limiter.window_seconds == 3600  # 1 hour (NFR-022)

    assert general_rate_limiter.limit == 200
    assert general_rate_limiter.window_seconds == 60  # 1 minute (NFR-022)


def test_sliding_window_thread_safety_concurrency():
    """Verify that concurrent requests under multithreaded contention do not breach the limit."""
    limit = 25
    limiter = SlidingWindowRateLimiter(limit=limit, window_seconds=60)
    key = "concurrent_user"

    num_threads = 60
    success_count = 0
    rejected_count = 0

    def worker():
        try:
            limiter.check_and_record(key)
            return True
        except AppError as e:
            if e.status_code == 429:
                return False
            raise

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(lambda _: worker(), range(num_threads)))

    success_count = sum(1 for r in results if r is True)
    rejected_count = sum(1 for r in results if r is False)

    assert success_count == limit, f"Expected exactly {limit} successes, got {success_count}"
    assert rejected_count == num_threads - limit, f"Expected {num_threads - limit} rejections, got {rejected_count}"


def test_trusted_proxy_ip_resolution_security():
    """Verify that proxy headers are accepted ONLY from trusted reverse proxies.

    Untrusted peers cannot spoof X-Forwarded-For or X-Real-IP.
    """
    settings = Settings(TRUSTED_PROXIES="10.0.0.1,127.0.0.1")

    # Case 1: Untrusted direct client connects from public IP 203.0.113.5
    # Attacker attempts to spoof X-Forwarded-For: 1.1.1.1
    req_untrusted = MagicMock()
    req_untrusted.client.host = "203.0.113.5"
    req_untrusted.headers = {"X-Forwarded-For": "1.1.1.1, 10.0.0.1"}

    resolved_ip = get_client_ip(req_untrusted, settings)
    assert resolved_ip == "203.0.113.5", "Untrusted peer must NOT have its X-Forwarded-For trusted"

    # Case 2: Connection from trusted proxy (e.g. internal reverse proxy 10.0.0.1)
    req_trusted = MagicMock()
    req_trusted.client.host = "10.0.0.1"
    req_trusted.headers = {"X-Forwarded-For": "198.51.100.42, 10.0.0.1"}

    resolved_trusted_ip = get_client_ip(req_trusted, settings)
    assert resolved_trusted_ip == "198.51.100.42", "Trusted proxy's client hop must be resolved"

    # Case 3: Connection from trusted proxy with X-Real-IP
    req_trusted_real = MagicMock()
    req_trusted_real.client.host = "127.0.0.1"
    req_trusted_real.headers = {"X-Real-IP": "198.51.100.88"}

    assert get_client_ip(req_trusted_real, settings) == "198.51.100.88"


def test_token_evasion_prevention():
    """Verify that unauthenticated attackers cannot evade the general limit

    by sending random or changing Bearer tokens.
    """
    settings = Settings()

    # Request with random fake token
    req_fake_token = MagicMock()
    req_fake_token.client.host = "203.0.113.99"
    req_fake_token.headers = {"Authorization": f"Bearer fake_token_{uuid.uuid4().hex}"}

    identity = get_client_identity(req_fake_token, settings)
    # Must fall back to client IP, preventing rate limit partition evasion
    assert identity == "ip:203.0.113.99"

    # Request with valid token
    user_id = uuid.uuid4()
    valid_token = create_access_token(user_id, "chef@example.com")
    req_valid = MagicMock()
    req_valid.client.host = "203.0.113.99"
    req_valid.headers = {"Authorization": f"Bearer {valid_token}"}

    valid_identity = get_client_identity(req_valid, settings)
    assert valid_identity == f"user:{user_id}"


def test_malformed_and_expired_token_handling():
    """Verify that malformed or non-JWT Bearer tokens do not cause 500 errors."""
    settings = Settings()

    req_malformed = MagicMock()
    req_malformed.client.host = "192.0.2.1"
    req_malformed.headers = {"Authorization": "Bearer not.a.valid.jwt.token"}

    identity = get_client_identity(req_malformed, settings)
    assert identity == "ip:192.0.2.1"


def test_general_rate_limiter_middleware_enforcement(client: TestClient):
    """Test that general rate limiter enforces 200 req/min and returns headers."""
    general_rate_limiter.clear()

    # Rapidly call a lightweight endpoint 200 times
    for _ in range(200):
        resp = client.get("/api/v1/ingredients?limit=1")
        assert resp.status_code == 200, f"Unexpected failure before limit: {resp.text}"

    # 201st request rejected with 429
    rejected = client.get("/api/v1/ingredients?limit=1")
    assert rejected.status_code == 429
    assert rejected.headers.get("Retry-After") is not None
    assert rejected.headers.get("X-Request-ID") is not None
    assert rejected.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "retry_after_seconds" in rejected.json()["error"]["details"]


def test_health_and_docs_exempt_from_rate_limiting(client: TestClient):
    """Health endpoints and OpenAPI documentation routes must never consume quota."""
    general_rate_limiter.clear()

    # Pre-exhaust limiter for testclient IP
    for _ in range(200):
        general_rate_limiter.check_and_record("ip:testclient")

    # Health check must still return 200
    health_resp = client.get("/api/health")
    assert health_resp.status_code == 200

    api_health_resp = client.get("/api/v1/health")
    assert api_health_resp.status_code == 200

    # OpenAPI schema docs must still return 200
    openapi_resp = client.get("/openapi.json")
    assert openapi_resp.status_code == 200


def test_single_worker_rate_limiting_preservation():
    """Demonstrates that a single worker architecture preserves exact global rate limits.

    Under in-process rate limiting (PRD Section 13.1), a single worker guarantees
    that all concurrent requests share the exact same state, strictly enforcing
    the target limit (e.g. 10 attempts for login, 20 for scans, 60 for recommendations)
    without leakage or quota multiplication.
    """
    limit = 10
    unified_limiter = SlidingWindowRateLimiter(limit=limit, window_seconds=60)
    user_key = "user:single_worker_test"

    # Exactly `limit` requests pass
    for _i in range(limit):
        unified_limiter.check_and_record(user_key)

    # Every subsequent request is rejected with HTTP 429
    with pytest.raises(AppError) as exc_info:
        unified_limiter.check_and_record(user_key)

    assert exc_info.value.status_code == 429
    assert exc_info.value.code == "RATE_LIMIT_EXCEEDED"


def test_multi_worker_state_partitioning_contrast():
    """Demonstrates why multi-worker setups require external shared storage (Redis).

    If multiple independent worker processes each maintain a process-local rate limiter,
    an attacker's traffic distributed round-robin across N workers would permit
    N * limit requests before all workers block the user.
    This proves why GUNICORN_WORKERS=1 is the required production configuration
    when using the in-process sliding-window rate limiter per PRD Section 13.1.
    """
    limit = 10
    num_workers = 4
    user_key = "user:multi_worker_attacker"

    # Simulate 4 independent worker processes, each with its own local limiter
    worker_limiters = [
        SlidingWindowRateLimiter(limit=limit, window_seconds=60)
        for _ in range(num_workers)
    ]

    # Distribute requests across workers round-robin
    total_passed = 0
    for req_idx in range(num_workers * limit):
        assigned_worker = worker_limiters[req_idx % num_workers]
        assigned_worker.check_and_record(user_key)
        total_passed += 1

    # In a 4-worker unshared setup, 40 requests passed instead of 10!
    assert total_passed == 40

    # Only on the 41st request do workers start blocking
    with pytest.raises(AppError):
        worker_limiters[0].check_and_record(user_key)

