from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "Linguaphilia"
    app_env: str = Field(default="development", alias="APP_ENV")
    database_url: str = Field(
        default="postgresql+asyncpg://literature:literature@localhost:5432/literature",
        alias="DATABASE_URL",
    )
    account_store_path: Path | None = Field(default=None, alias="ACCOUNT_STORE_PATH")
    gutenberg_raw_dir: Path = Field(
        default=PROJECT_ROOT / "data/raw/gutenberg", alias="GUTENBERG_RAW_DIR"
    )
    processed_data_dir: Path = Field(default=PROJECT_ROOT / "data/processed", alias="PROCESSED_DATA_DIR")
    interaction_log_path: Path = Field(
        default=PROJECT_ROOT / "data/processed/interactions.jsonl", alias="INTERACTION_LOG_PATH"
    )
    embedding_provider: str = Field(default="openai", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    embedding_dimensions: int = Field(default=1536, alias="EMBEDDING_DIMENSIONS")
    recommendation_vector_backend: str = Field(default="auto", alias="RECOMMENDATION_VECTOR_BACKEND")
    recommendation_vector_candidate_limit: int = Field(
        default=600, alias="RECOMMENDATION_VECTOR_CANDIDATE_LIMIT"
    )
    media_storage_backend: str = Field(default="inline", alias="MEDIA_STORAGE_BACKEND")
    media_upload_dir: Path = Field(default=PROJECT_ROOT / "data/uploads", alias="MEDIA_UPLOAD_DIR")
    media_public_base_url: str = Field(default="http://localhost:8000/media", alias="MEDIA_PUBLIC_BASE_URL")
    object_storage_bucket: str | None = Field(default=None, alias="OBJECT_STORAGE_BUCKET")
    object_storage_region: str | None = Field(default=None, alias="OBJECT_STORAGE_REGION")
    object_storage_endpoint_url: str | None = Field(default=None, alias="OBJECT_STORAGE_ENDPOINT_URL")
    object_storage_access_key_id: str | None = Field(default=None, alias="OBJECT_STORAGE_ACCESS_KEY_ID")
    object_storage_secret_access_key: str | None = Field(
        default=None, alias="OBJECT_STORAGE_SECRET_ACCESS_KEY"
    )
    object_storage_public_base_url: str | None = Field(
        default=None, alias="OBJECT_STORAGE_PUBLIC_BASE_URL"
    )
    object_storage_corpus_prefix: str = Field(
        default="corpus", alias="OBJECT_STORAGE_CORPUS_PREFIX"
    )
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        alias="CORS_ORIGINS",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
