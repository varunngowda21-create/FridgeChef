import pytest

from app.core.config import Settings, get_settings


def test_settings_loaded():
    settings = get_settings()
    assert settings.DATABASE_URL is not None
    assert "postgresql" in settings.DATABASE_URL
    assert settings.ENVIRONMENT in ("development", "test", "production")
    assert settings.AUTH_REFRESH_TRANSPORT == "cookie"


def test_cors_origins_parsing():
    settings = Settings(
        DATABASE_URL="postgresql+psycopg://test:test@localhost:5432/test",
        GROQ_API_KEY="test_key",
        JWT_SECRET="test_jwt_secret_with_adequate_entropy_and_bits",
        CORS_ORIGINS="http://localhost:5173, http://localhost:3000,https://app.fridgechef.com",
    )
    origins = settings.cors_origins_list
    assert len(origins) == 3
    assert "http://localhost:5173" in origins
    assert "https://app.fridgechef.com" in origins


def test_invalid_refresh_transport():
    with pytest.raises(ValueError):
        Settings(
            DATABASE_URL="postgresql+psycopg://test:test@localhost:5432/test",
            GROQ_API_KEY="test_key",
            JWT_SECRET="test_jwt_secret_with_adequate_entropy_and_bits",
            AUTH_REFRESH_TRANSPORT="localstorage",  # Invalid per PRD Section 12.5 & AGENTS.md
        )
