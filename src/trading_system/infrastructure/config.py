"""Configuration management for Trading System Engine service."""
from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with multi-instance support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application settings
    version: str = "0.1.0"
    environment: Literal["development", "testing", "production", "docker"] = "development"
    debug: bool = False

    # Server settings
    host: str = "0.0.0.0"
    http_port: int = Field(default=8083, gt=0, le=65535)  # Trading Engine HTTP port
    grpc_port: int = Field(default=50053, gt=0, le=65535)  # Trading Engine gRPC port

    # Logging settings
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    # External services
    redis_url: str = "redis://localhost:6379"
    postgres_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/trading_ecosystem"
    service_registry_url: str = "http://localhost:8080"

    # Service Identity (NEW for multi-instance support)
    service_name: str = "trading-system-engine"
    service_instance_name: str = Field(default="")  # Auto-derived from service_name if empty
    service_version: str = "0.1.0"
    health_check_interval: int = 30  # seconds
    registration_retry_interval: int = 5  # seconds

    # OpenTelemetry settings
    otel_service_name: str = "trading-system-engine"
    otel_exporter_endpoint: str = "http://localhost:4317"
    otel_insecure: bool = True

    # Performance settings
    worker_pool_size: int = 10
    max_concurrent_requests: int = 100
    request_timeout: float = 30.0

    # Trading engine settings
    max_position_size: float = 1000000.0  # $1M default
    risk_limit_threshold: float = 500000.0  # $500K default
    order_timeout_seconds: int = 30  # seconds
    strategy_cooldown_seconds: int = 60  # 1 minute

    @field_validator('log_level', mode='before')
    @classmethod
    def normalize_log_level(cls, v: Any) -> str:
        """Normalize log level to uppercase for Literal validation.

        This allows environment variables like LOG_LEVEL=info to work correctly,
        as Literal validation requires exact case matching.
        """
        if isinstance(v, str):
            return v.upper()
        return v

    def model_post_init(self, __context: Any) -> None:
        """Derive instance-specific configuration after model initialization.

        This hook runs after Pydantic validation and automatically derives
        service_instance_name from service_name if not explicitly provided.
        """
        if not self.service_instance_name:
            self.service_instance_name = self.service_name


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()