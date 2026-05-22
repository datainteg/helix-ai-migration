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


settings = Settings()
