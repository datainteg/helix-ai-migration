from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    APP_NAME: str = "Helix Migration"
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "change_me"

    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    DATABASE_URL: str = "postgresql://helix:helix_password@localhost:5432/helix_metadata"

    REDIS_URL: str = "redis://localhost:6379/0"

    TEMPORAL_ADDRESS: str = "localhost:7233"
    TEMPORAL_NAMESPACE: str = "default"

    JWT_SECRET_KEY: str = "change_me"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ENCRYPTION_KEY: str = "change_me_32_byte_key"

    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]

    DEFAULT_LLM_PROVIDER: str = "openai"
    DEFAULT_LLM_MODEL: str = "gpt-4.1"

    ARTIFACT_STORAGE_PROVIDER: str = "local"
    ARTIFACT_STORAGE_PATH: str = "./data/artifacts"
    MAX_UPLOAD_MB: int = 25

    SAFE_EXECUTION_MODE: str = "analysis_only"

    SENTRY_DSN: str = ""
    OTEL_ENDPOINT: str = ""

    def model_post_init(self, _context) -> None:
        """Validate security-critical settings in production."""
        if self.APP_ENV == "production":
            insecure_defaults = []
            if self.JWT_SECRET_KEY == "change_me":
                insecure_defaults.append("JWT_SECRET_KEY")
            if self.ENCRYPTION_KEY == "change_me_32_byte_key":
                insecure_defaults.append("ENCRYPTION_KEY")
            if self.APP_SECRET_KEY == "change_me":
                insecure_defaults.append("APP_SECRET_KEY")
            if insecure_defaults:
                raise ValueError(
                    f"In production, the following must be changed from defaults: {', '.join(insecure_defaults)}. "
                    "Generate secure values with: python -c 'import secrets; print(secrets.token_hex(32))'"
                )
            # Reject wildcard CORS origins in production
            if "*" in self.CORS_ORIGINS:
                raise ValueError("CORS_ORIGINS must not contain '*' in production")
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
