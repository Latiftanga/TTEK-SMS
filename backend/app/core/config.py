"""
Application settings — loaded from environment variables (and .env in development).

All fields map directly to environment variable names (case-insensitive).
Fields with insecure defaults will raise ValueError at startup when
app_env='production', preventing accidental deployment with test secrets.

CORS
----
Set CORS_ORIGINS as a JSON array in the environment:
    CORS_ORIGINS='["https://app.tagnatek.com"]'
Defaults to localhost dev/preview ports, which is correct for local development.

DATABASE URL
------------
Either set DATABASE_URL explicitly, or set the individual postgres_* fields
and the URL is built automatically.  Both approaches are supported.
"""
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Fields whose default values are insecure and must be overridden in production.
_INSECURE_DEFAULTS: dict[str, str] = {
    "app_secret_key": "change-me",
    "hmac_secret_key": "change-me-hmac",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = "development"
    app_secret_key: str = "change-me"
    app_debug: bool = True
    # Used to build absolute URLs (e.g. logo_url in branding response).
    # Override in production: APP_BASE_URL=https://api.ttek-sms.com
    app_base_url: str = "http://localhost:8000"

    # ── Database ─────────────────────────────────────────────────────────────
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "ttek_sms"
    postgres_user: str = "ttek"
    postgres_password: str = "changeme"
    # Leave empty to auto-build from the postgres_* fields above.
    database_url: str = ""

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"

    # ── JWT ──────────────────────────────────────────────────────────────────
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    jwt_algorithm: str = "HS256"

    # ── Rate limiting ─────────────────────────────────────────────────────────
    rate_limit_per_minute: int = 100

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:4173"]

    # ── Storage ──────────────────────────────────────────────────────────────
    storage_backend: Literal["LOCAL", "CLOUDFLARE_R2"] = "LOCAL"
    local_upload_dir: str = "./uploads"
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    # Public base URL for R2 files (e.g. https://cdn.ttek-sms.com).
    # Unused when storage_backend=LOCAL.
    r2_public_url: str = ""

    # ── Sentry ───────────────────────────────────────────────────────────────
    sentry_dsn: str = ""

    # ── HMAC (QR verification tokens) ────────────────────────────────────────
    hmac_secret_key: str = "change-me-hmac"

    # ── First superadmin (used only by create_superadmin.py) ─────────────────
    superadmin_email: str = "admin@tagnatek.com"
    superadmin_password: str = "changeme"

    # ── Validators ───────────────────────────────────────────────────────────

    @field_validator("database_url", mode="before")
    @classmethod
    def build_database_url(cls, v: str, info) -> str:
        """Build the asyncpg URL from component fields when DATABASE_URL is not set."""
        if v:
            return v
        data = info.data
        user = data.get("postgres_user", "ttek")
        password = data.get("postgres_password", "changeme")
        host = data.get("postgres_host", "db")
        port = data.get("postgres_port", 5432)
        db = data.get("postgres_db", "ttek_sms")
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """Refuse to start in production if any secret is still the insecure default."""
        if self.app_env != "production":
            return self
        for field, insecure_value in _INSECURE_DEFAULTS.items():
            if getattr(self, field) == insecure_value:
                raise ValueError(
                    f"'{field}' must be changed from its insecure default before deploying "
                    f"to production.  Set it via the {field.upper()} environment variable."
                )
        return self

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


settings = Settings()
