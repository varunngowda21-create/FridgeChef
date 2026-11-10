"""Tests for reverse proxy trust, X-Forwarded-Proto spoofing protection, and HSTS emission.

PRD References: Section 12.5, Section 15.1, Section 15.3, RFC 6797 Section 7.2.
"""

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.ratelimit import get_client_ip
from app.core.security import is_ip_trusted
from app.main import app


def test_is_ip_trusted_exact_and_cidr():
    trusted = {"127.0.0.1", "::1", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"}

    # Loopback and private subnets
    assert is_ip_trusted("127.0.0.1", trusted) is True
    assert is_ip_trusted("::1", trusted) is True
    assert is_ip_trusted("10.5.2.1", trusted) is True
    assert is_ip_trusted("172.28.0.4", trusted) is True
    assert is_ip_trusted("192.168.1.50", trusted) is True
    assert is_ip_trusted("testclient", trusted) is True
    assert is_ip_trusted("localhost", trusted) is True

    # Untrusted public IPs
    assert is_ip_trusted("203.0.113.50", trusted) is False
    assert is_ip_trusted("8.8.8.8", trusted) is False
    assert is_ip_trusted("198.51.100.2", trusted) is False


def test_untrusted_peer_cannot_spoof_client_ip():
    class DummyClient:
        host = "203.0.113.50"

    class DummyRequest:
        client = DummyClient()
        headers = {"X-Forwarded-For": "1.2.3.4", "X-Real-IP": "1.2.3.4"}

    settings = Settings(
        GROQ_API_KEY="test_key",
        DATABASE_URL="sqlite:///:memory:",
        JWT_SECRET="test_secret_32_characters_long_for_test",
        TRUSTED_PROXIES="127.0.0.1,::1,172.16.0.0/12",
    )

    # Untrusted peer: headers are ignored, actual socket host is returned
    client_ip = get_client_ip(DummyRequest(), settings)  # type: ignore[arg-type]
    assert client_ip == "203.0.113.50"

    # Trusted peer: proxy header is respected
    class TrustedClient:
        host = "172.28.0.4"

    class TrustedRequest:
        client = TrustedClient()
        headers = {"X-Forwarded-For": "198.51.100.99, 172.28.0.4"}

    trusted_ip = get_client_ip(TrustedRequest(), settings)  # type: ignore[arg-type]
    assert trusted_ip == "198.51.100.99"


def test_direct_http_request_in_production_never_emits_hsts(monkeypatch):
    """RFC 6797 Sec 7.2: An HTTP host MUST NOT include STS header over non-secure transport."""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "APP_ENV", "production")

    client = TestClient(app, base_url="http://testserver")
    response = client.get("/api/health")
    assert response.status_code == 200

    # Since connection is plain HTTP, Strict-Transport-Security must NOT be emitted
    assert "Strict-Transport-Security" not in response.headers


def test_https_request_in_production_emits_hsts(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "APP_ENV", "production")

    client = TestClient(app, base_url="https://testserver")
    response = client.get("/api/health")
    assert response.status_code == 200

    # Genuine HTTPS in production: HSTS must be emitted
    assert "Strict-Transport-Security" in response.headers
    assert "max-age=31536000" in response.headers["Strict-Transport-Security"]


def test_spoofed_forwarded_proto_from_untrusted_peer_ignored(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "APP_ENV", "production")

    # Untrusted client sends X-Forwarded-Proto: https
    client = TestClient(app, base_url="http://testserver", client=("203.0.113.10", 54321))
    response = client.get("/api/health", headers={"X-Forwarded-Proto": "https"})
    assert response.status_code == 200

    # Spoofed proto from untrusted peer must be ignored: no HSTS emitted
    assert "Strict-Transport-Security" not in response.headers


def test_development_environment_never_emits_hsts(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "APP_ENV", "development")

    client = TestClient(app, base_url="https://testserver")
    response = client.get("/api/health")
    assert response.status_code == 200
    assert "Strict-Transport-Security" not in response.headers
