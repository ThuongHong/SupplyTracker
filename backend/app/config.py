from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from pydantic import HttpUrl, PostgresDsn, RedisDsn
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import EnvSettingsSource

# Fields stored as comma-separated strings in the environment.
_CSV_ENV_FIELDS: frozenset[str] = frozenset(
    ("cors_origins", "fred_series", "bunker_ports", "bunker_fuel_types")
)


def _split_csv(value: Any) -> list[str]:
    """Split a comma-separated string into a stripped list of non-empty items."""
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return value
    return []


class _CsvAwareEnvSource(EnvSettingsSource):
    """Custom env source that parses designated fields as CSV instead of JSON."""

    def prepare_field_value(
        self,
        field_name: str,
        field: FieldInfo,
        value: Any,
        value_is_complex: bool,
    ) -> Any:
        if field_name in _CSV_ENV_FIELDS and isinstance(value, str):
            return _split_csv(value)
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: PostgresDsn

    # Redis
    redis_url: RedisDsn
    celery_broker_url: RedisDsn
    celery_result_backend: RedisDsn

    # Backend
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: list[str] = []
    log_level: str = "INFO"
    environment: Literal["development", "staging", "production"] = "development"
    sync_bearer_token: str = ""

    # PortWatch
    portwatch_base_url: HttpUrl
    portwatch_rate_limit_per_minute: int = 60

    # FRED
    fred_api_key: str = ""
    fred_series: list[str] = []

    # Freight
    fbx_source_url: str = ""
    wci_source_url: str = ""

    # Bunker
    bunker_ports: list[str] = []
    bunker_fuel_types: list[str] = []

    # LLM (DashScope Qwen)
    dashscope_api_key: str = ""
    dashscope_base_url: HttpUrl
    qwen_primary_model: str = "qwen-plus"
    qwen_fallback_model: str = "qwen-turbo"
    llm_reasoning_enabled: bool = False
    llm_request_timeout_s: int = 60
    decision_brief_cache_ttl_s: int = 3600
    chat_rate_limit_per_5min: int = 20

    # SMTP
    smtp_host: str
    smtp_port: int

    # Frontend
    vite_api_base_url: HttpUrl

    @classmethod
    def settings_customise_sources(  # type: ignore[override]
        cls,
        settings_cls: type[BaseSettings],
        init_settings: Any,
        env_settings: Any,
        dotenv_settings: Any,
        file_secret_settings: Any,
    ) -> tuple[Any, ...]:
        return (
            init_settings,
            _CsvAwareEnvSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # args come from env/dotenv
