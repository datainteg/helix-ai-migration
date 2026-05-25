import secrets
from pydantic_settings import BaseSettings
from typing import List


# Ephemeral dev-only fallback secrets. Generated once per process when no env
# value is provided. Production blocks these via model_post_init below.
_EPHEMERAL_JWT_SECRET = secrets.token_hex(32)
_EPHEMERAL_APP_SECRET = secrets.token_hex(32)
_EPHEMERAL_AUDIT_HMAC = secrets.token_hex(32)


def _ephemeral_fernet_key() -> str:
    try:
        from cryptography.fernet import Fernet
        return Fernet.generate_key().decode()
    except Exception:
        import base64
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


_EPHEMERAL_ENCRYPTION_KEY = _ephemeral_fernet_key()


class Settings(BaseSettings):
    # `extra=ignore` so the same .env can hold vars consumed by other
    # services (Postgres, Temporal compose env, etc.) without rejecting them.
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    APP_NAME: str = "Helix Migration"
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = _EPHEMERAL_APP_SECRET

    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    DATABASE_URL: str = "postgresql://helix:helix_password@localhost:5432/helix_metadata"

    REDIS_URL: str = "redis://localhost:6379/0"

    TEMPORAL_ADDRESS: str = "localhost:7233"
    TEMPORAL_NAMESPACE: str = "default"

    JWT_SECRET_KEY: str = _EPHEMERAL_JWT_SECRET
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ENCRYPTION_KEY: str = _EPHEMERAL_ENCRYPTION_KEY
    AUDIT_HMAC_KEY: str = _EPHEMERAL_AUDIT_HMAC

    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    CORS_ORIGIN_REGEX: str = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

    DEFAULT_LLM_PROVIDER: str = "openai"
    DEFAULT_LLM_MODEL: str = "gpt-4.1"

    ARTIFACT_STORAGE_PROVIDER: str = "local"
    ARTIFACT_STORAGE_PATH: str = "./data/artifacts"
    MAX_UPLOAD_MB: int = 25

    SAFE_EXECUTION_MODE: str = "analysis_only"

    SENTRY_DSN: str = ""
    OTEL_ENDPOINT: str = ""

    # Email (SMTP or SendGrid)
    EMAIL_ENABLED: bool = False
    EMAIL_FROM: str = "noreply@helix-migration.app"
    EMAIL_FROM_NAME: str = "Helix Migration"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_TLS: bool = True
    SENDGRID_API_KEY: str = ""  # If set, uses SendGrid instead of SMTP
    FRONTEND_URL: str = "http://localhost:3000"

    def model_post_init(self, _context) -> None:
        """Validate security-critical settings in production."""
        if self.APP_ENV == "production":
            insecure_defaults = []
            # Legacy "change_me" strings must never reach prod.
            if self.JWT_SECRET_KEY in ("change_me", _EPHEMERAL_JWT_SECRET):
                insecure_defaults.append("JWT_SECRET_KEY")
            if self.ENCRYPTION_KEY in ("change_me_32_byte_key", _EPHEMERAL_ENCRYPTION_KEY):
                insecure_defaults.append("ENCRYPTION_KEY")
            if self.APP_SECRET_KEY in ("change_me", _EPHEMERAL_APP_SECRET):
                insecure_defaults.append("APP_SECRET_KEY")
            if self.AUDIT_HMAC_KEY in ("change_me", _EPHEMERAL_AUDIT_HMAC):
                insecure_defaults.append("AUDIT_HMAC_KEY")
            if insecure_defaults:
                raise ValueError(
                    f"In production, the following must be set explicitly: {', '.join(insecure_defaults)}. "
                    "Generate secure values with: python -c 'import secrets; print(secrets.token_hex(32))'"
                )
            # AUDIT_HMAC_KEY must be distinct from JWT_SECRET_KEY so JWT rotation
            # does not invalidate the audit chain.
            if self.AUDIT_HMAC_KEY == self.JWT_SECRET_KEY:
                raise ValueError("AUDIT_HMAC_KEY must differ from JWT_SECRET_KEY")
            # Reject wildcard CORS origins in production
            if "*" in self.CORS_ORIGINS:
                raise ValueError("CORS_ORIGINS must not contain '*' in production")
            # Disallow regex-based origins in production. Use explicit allowlist only.
            if self.CORS_ORIGIN_REGEX:
                raise ValueError("CORS_ORIGIN_REGEX must be empty in production; use explicit CORS_ORIGINS")
            # Validate ENCRYPTION_KEY is a proper base64-encoded 32-byte Fernet key
            import base64
            try:
                decoded = base64.urlsafe_b64decode(self.ENCRYPTION_KEY + "==")
                if len(decoded) != 32:
                    raise ValueError
            except Exception:
                raise ValueError(
                    "ENCRYPTION_KEY must be a base64-encoded 32-byte key. "
                    "Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
                )


settings = Settings()
