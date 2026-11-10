from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required settings (PRD Section 13.3)
    GROQ_API_KEY: str
    DATABASE_URL: str
    JWT_SECRET: str

    # Environment & Logging
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = "http://localhost:5173"

    # AI / Groq Model Defaults (PRD Section 9.1)
    GROQ_VISION_MODEL: str = "qwen/qwen3.8-27b"
    GROQ_TEXT_MODEL: str = "openai/gpt-oss-120b"
    GROQ_TIMEOUT_SECONDS: int = 20
    GROQ_MAX_RETRIES: int = 2
    LLM_MONTHLY_BUDGET_USD: float | None = None

    # Media & Uploads (PRD Section 13.3)
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_MB: int = 8

    # Auth & Tokens
    ACCESS_TOKEN_MINUTES: int = 60
    REFRESH_TOKEN_DAYS: int = 30
    AUTH_REFRESH_TRANSPORT: str = "cookie"

    # Rate Limits (PRD Section 7.3, NFR-022)
    RATE_LIMIT_SCANS_PER_DAY: int = 20
    RATE_LIMIT_RECS_PER_HOUR: int = 60
    RATE_LIMIT_GENERAL_PER_MINUTE: int = 200

    # Reverse Proxy Settings (PRD Section 15.1, 15.3)
    TRUSTED_PROXIES: str = "127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"

    # Product Settings (Configurable limits)
    DASHBOARD_RECOMMENDATIONS_LIMIT: int = 3

    @field_validator("GROQ_API_KEY")
    @classmethod
    def validate_groq_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("GROQ_API_KEY must not be empty.")
        val = v.strip()
        if val.startswith("REPLACE_WITH"):
            raise ValueError("GROQ_API_KEY cannot be a placeholder value.")
        return val

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("DATABASE_URL must not be empty.")
        val = v.strip()
        if "REPLACE_WITH" in val or "staging_secure_password_replace" in val:
            raise ValueError("DATABASE_URL cannot contain placeholder passwords or replacement templates.")
        return val

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if not v or len(v.strip()) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters long.")
        val = v.strip()
        if val.startswith("REPLACE_WITH") or "placeholder" in val.lower():
            raise ValueError("JWT_SECRET cannot be a placeholder value.")
        return val

    @field_validator("AUTH_REFRESH_TRANSPORT")
    @classmethod
    def validate_refresh_transport(cls, v: str) -> str:
        valid_transports = {"cookie", "sessionstorage"}
        if v.lower() not in valid_transports:
            raise ValueError(f"AUTH_REFRESH_TRANSPORT must be one of {valid_transports}, got '{v}'.")
        return v.lower()

    @property
    def ENVIRONMENT(self) -> str:
        return self.APP_ENV

    @property
    def cors_origins_list(self) -> list[str]:
        if not self.CORS_ORIGINS:
            return ["http://localhost:5173"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def trusted_proxies_list(self) -> set[str]:
        if not self.TRUSTED_PROXIES:
            return {"127.0.0.1", "::1"}
        return {ip.strip() for ip in self.TRUSTED_PROXIES.split(",") if ip.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
