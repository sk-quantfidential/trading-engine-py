"""Configuration management for Trading System Engine service."""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application settings
    version: str = "0.1.0"
    environment: Literal["development", "testing", "production"] = "development"
    debug: bool = False

    # Server settings
    host: str = "0.0.0.0"
    http_port: int = Field(default=8081, gt=0, le=65535)
    grpc_port: int = Field(default=9091, gt=0, le=65535)

    # Logging settings
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    # External services
    redis_url: str = "redis://localhost:6379"
    exchange_api_url: str = "http://localhost:8082"
    market_data_api_url: str = "http://localhost:8080"

    # Trading settings
    default_position_size: float = 1000.0  # Default position size
    max_position_size: float = 10000.0  # Maximum position size
    trading_enabled: bool = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()