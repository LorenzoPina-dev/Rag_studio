import json
import tempfile
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _default_dataset_roots() -> list[Path]:
    """Repository root (from this file) plus the OS temp dir used by local tests."""
    return [Path(__file__).resolve().parents[3], Path(tempfile.gettempdir()).resolve()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "RAG Studio API"
    app_env: str = "development"
    app_debug: bool = False
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])

    # When set, every mutating API request must send the same value in X-API-Token.
    api_access_token: str | None = None

    # RAG corpus shared by runtime, comparison and Python export
    rag_dataset_path: Path = Path(__file__).resolve().parents[2] / "data" / "documents.json"

    # Local connectors may only read inside these roots (comma-separated or JSON env override).
    dataset_allowed_roots: Annotated[list[Path], NoDecode] = Field(
        default_factory=_default_dataset_roots
    )

    # HTTP connectors must not reach private/loopback/link-local networks unless explicitly allowed.
    allow_private_connectors: bool = False

    @field_validator("dataset_allowed_roots", mode="before")
    @classmethod
    def _parse_dataset_roots(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, str):
            return [parsed]
        return [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]

    # Persistence / infrastructure backends
    persistence_backend: Literal["memory", "database"] = "memory"
    database_url: str = "postgresql+psycopg://ragstudio:ragstudio@localhost:5432/ragstudio"
    db_echo: bool = False
    db_pool_pre_ping: bool = True

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    artifact_store_backend: Literal["memory", "minio", "filesystem"] = "memory"
    artifact_root_dir: str = "./.artifacts"
    artifact_retention_days: int = 30
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "ragstudio"
    s3_secret_key: str = "ragstudio-secret"
    s3_bucket_artifacts: str = "ragstudio-artifacts"
    s3_region: str = "us-east-1"
    s3_secure: bool = False

    secret_key: str = "change-me-in-production"
    encryption_key: str = "change-me-32-byte-key-base64-or-fernet"

    # Chiave Fernet per cifrare provider_settings.json a riposo. Se vuota il file resta in chiaro.
    provider_settings_key: str | None = None

    otel_enabled: bool = False
    otel_service_name: str = "rag-studio-backend"
    otel_exporter_otlp_endpoint: str | None = None

    execution_default_timeout_seconds: int = 600
    execution_node_timeout_seconds: float = 300.0
    execution_retry_max_attempts: int = 1
    execution_retry_backoff_seconds: float = 0.0
    execution_max_parallel_nodes: int = 4
    custom_node_runtime: str = "isolated-worker"

    # Stream coordination (idempotent SSE across workers)
    # Shared coordination backend for stream ownership and execution slots
    stream_coordination_backend: Literal["memory", "redis"] = "memory"
    stream_lock_ttl_seconds: int = 600
    stream_wait_timeout_seconds: float = 30.0
    execution_max_parallel_executions: int = 2
    execution_slot_ttl_seconds: int = 600

    @model_validator(mode="after")
    def _require_production_hardening(self) -> "Settings":
        """In produzione auth e root dataset espliciti sono obbligatori (fail fast)."""
        if self.app_env.strip().lower() != "production":
            return self
        if not (self.api_access_token or "").strip():
            raise ValueError(
                "API_ACCESS_TOKEN è obbligatorio con APP_ENV=production: "
                "le richieste mutanti devono essere protette."
            )
        if "dataset_allowed_roots" not in self.model_fields_set or not self.dataset_allowed_roots:
            raise ValueError(
                "DATASET_ALLOWED_ROOTS deve essere configurata in modo esplicito e non vuota "
                "con APP_ENV=production."
            )
        return self


settings = Settings()
