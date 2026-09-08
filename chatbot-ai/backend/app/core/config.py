from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, loaded from environment variables / .env.

    Secrets (DB password, JWT secret, OpenAI key, config-encryption key) must
    never be logged or returned by any API response.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: str = "development"
    APP_NAME: str = "AI Chatbot Platform"
    API_PREFIX: str = "/api"

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/chatbot"

    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET: str = "CHANGE-ME-IN-PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Symmetric key (Fernet) used to encrypt secrets stored in the database,
    # e.g. SMTP password. Generate with cryptography.fernet.Fernet.generate_key().
    CONFIG_ENCRYPTION_KEY: str = ""

    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str | None = None
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_EMBEDDING_DIMENSIONS: int = 1536

    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    WIDGET_ALLOWED_ORIGINS: list[str] = ["*"]

    STORAGE_BACKEND: str = "local"
    STORAGE_LOCAL_PATH: str = "/data/storage"
    MAX_UPLOAD_SIZE_MB: int = 20

    RATE_LIMIT_WIDGET_PER_MINUTE: int = 30

    FRONTEND_BASE_URL: str = "http://localhost:5173"
    WIDGET_SCRIPT_BASE_URL: str = "http://localhost:8000"

    # SMSC API integration. These only seed the smsc_settings DB row the
    # first time it's created — after that, the admin panel (Settings ->
    # SMSC Integration) is the source of truth and can change them without
    # a redeploy. The chatbot never connects to the SMSC MySQL database
    # directly; this base URL/key is the only address it ever talks to.
    SMSC_API_BASE_URL: str = ""
    SMSC_API_KEY: str = ""
    SMSC_API_TIMEOUT: int = 10
    SMSC_SESSION_EXPIRE_MINUTES: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
