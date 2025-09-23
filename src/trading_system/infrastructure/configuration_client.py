#!/usr/bin/env python3
"""
Configuration Service Client

This module provides centralized configuration management for the trading engine service.
It includes caching, validation, environment support, and service discovery integration.

Key Features:
- ConfigurationServiceClient: HTTP client for configuration service
- ConfigurationValue: Validated configuration data model with type conversions
- Caching: In-memory cache with TTL and statistics
- Service Discovery: Redis-based endpoint resolution
- Error Handling: Comprehensive ConfigurationError with context
- Performance Monitoring: Cache statistics and hit rate tracking
"""

import asyncio
import httpx
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Union
from datetime import datetime, timedelta

import structlog

from .config import Settings
from .service_discovery import ServiceDiscovery, ServiceInfo
from .constants import (
    DEFAULT_CACHE_TTL_SECONDS,
    VALID_CONFIG_TYPES,
    DEFAULT_CONFIG_SERVICE_PORT,
    CONNECTION_TIMEOUT as DEFAULT_REQUEST_TIMEOUT
)

logger = structlog.get_logger()


class ConfigurationError(Exception):
    """Configuration service related errors."""

    def __init__(self, message: str, key: Optional[str] = None, status_code: Optional[int] = None):
        super().__init__(message)
        self.key = key
        self.status_code = status_code

    def __str__(self):
        base_message = super().__str__()
        if self.key:
            return f"{base_message} (key: {self.key})"
        return base_message


@dataclass
class ConfigurationValue:
    """
    Represents a configuration value with validation and type conversion.

    Attributes:
        key: Configuration key (e.g., 'trading.position_limits.max_size')
        value: Configuration value as string
        type: Configuration type ('string', 'number', 'boolean', 'json')
        environment: Environment name (default: 'production')
        retrieved_at: Timestamp when value was retrieved
    """
    key: str
    value: str
    type: str
    environment: str = "production"
    retrieved_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Validate configuration type on creation."""
        if self.type not in VALID_CONFIG_TYPES:
            raise ValueError(f"Invalid configuration type: {self.type}. Valid types: {VALID_CONFIG_TYPES}")

    def validate(self) -> bool:
        """
        Validate configuration value.

        Returns:
            True if configuration is valid

        Raises:
            ValueError: If validation fails
        """
        if not self.key:
            raise ValueError("Configuration key cannot be empty")

        if not self.value:
            raise ValueError("Configuration value cannot be empty")

        if self.type not in VALID_CONFIG_TYPES:
            raise ValueError(f"Invalid configuration type: {self.type}")

        # Test type conversions to ensure value is compatible
        try:
            if self.type == "number":
                float(self.value)
            elif self.type == "boolean":
                self._parse_boolean(self.value)
            elif self.type == "json":
                json.loads(self.value)
        except (ValueError, json.JSONDecodeError) as e:
            raise ValueError(f"Configuration value '{self.value}' is not valid for type '{self.type}': {e}")

        return True

    def as_string(self) -> str:
        """Convert configuration value to string."""
        return self.value

    def as_float(self) -> float:
        """Convert configuration value to float."""
        try:
            return float(self.value)
        except ValueError as e:
            raise ValueError(f"Cannot convert '{self.value}' to float: {e}")

    def as_int(self) -> int:
        """Convert configuration value to integer."""
        try:
            return int(float(self.value))  # Handle decimal strings
        except ValueError as e:
            raise ValueError(f"Cannot convert '{self.value}' to int: {e}")

    def as_bool(self) -> bool:
        """Convert configuration value to boolean."""
        return self._parse_boolean(self.value)

    def as_json(self) -> Dict[str, Any]:
        """Convert configuration value to JSON/dict."""
        try:
            return json.loads(self.value)
        except json.JSONDecodeError as e:
            raise ValueError(f"Cannot convert '{self.value}' to JSON: {e}")

    @staticmethod
    def _parse_boolean(value: str) -> bool:
        """Parse string to boolean."""
        if value.lower() in ('true', '1', 'yes', 'on', 'enabled'):
            return True
        elif value.lower() in ('false', '0', 'no', 'off', 'disabled'):
            return False
        else:
            raise ValueError(f"Cannot convert '{value}' to boolean")


@dataclass
class _CacheEntry:
    """Internal cache entry with TTL tracking."""
    value: ConfigurationValue
    expires_at: datetime


class ConfigurationServiceClient:
    """
    Configuration service HTTP client with caching and service discovery.

    This client provides centralized configuration management with:
    - HTTP-based configuration retrieval
    - In-memory caching with TTL
    - Service discovery integration
    - Performance monitoring and statistics
    - Comprehensive error handling
    """

    def __init__(
        self,
        settings: Settings,
        service_discovery: Optional[ServiceDiscovery] = None,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT
    ):
        """
        Initialize configuration service client.

        Args:
            settings: Application settings
            service_discovery: Optional service discovery client
            cache_ttl_seconds: Cache TTL in seconds
            request_timeout: HTTP request timeout in seconds
        """
        self.settings = settings
        self.service_discovery = service_discovery
        self._cache_ttl = cache_ttl_seconds
        self._request_timeout = request_timeout

        # Cache management
        self._cache: Dict[str, _CacheEntry] = {}
        self.cache_hits = 0
        self._cache_misses = 0

        # HTTP client (created lazily)
        self._client: Optional[httpx.AsyncClient] = None

        self._logger = logger.bind(
            component="configuration_client",
            service="trading-engine",
            environment=settings.environment
        )

        self._logger.info(
            "Configuration client initialized",
            cache_ttl_seconds=cache_ttl_seconds,
            request_timeout=request_timeout,
            has_service_discovery=service_discovery is not None
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            timeout = httpx.Timeout(self._request_timeout)
            self._client = httpx.AsyncClient(
                timeout=timeout,
                headers={"User-Agent": "trading-engine-configuration-client/1.0"}
            )
        return self._client

    async def _get_service_endpoint(self) -> str:
        """
        Get configuration service endpoint.

        Returns:
            Configuration service HTTP endpoint URL
        """
        if self.service_discovery:
            try:
                service_info = await self.service_discovery.get_service("configuration-service")
                endpoint = f"http://{service_info.host}:{service_info.http_port}"
                self._logger.debug(
                    "Resolved configuration service endpoint via service discovery",
                    endpoint=endpoint
                )
                return endpoint
            except Exception as e:
                self._logger.warning(
                    "Failed to resolve configuration service via service discovery, using fallback",
                    error=str(e)
                )

        # Fallback to default endpoint
        fallback_endpoint = f"http://localhost:{DEFAULT_CONFIG_SERVICE_PORT}"
        self._logger.debug(
            "Using fallback configuration service endpoint",
            endpoint=fallback_endpoint
        )
        return fallback_endpoint

    def _get_from_cache(self, key: str) -> Optional[ConfigurationValue]:
        """
        Get configuration from cache.

        Args:
            key: Configuration key

        Returns:
            Cached configuration value or None if not found/expired
        """
        entry = self._cache.get(key)
        if entry is None:
            return None

        # Check TTL
        if datetime.utcnow() > entry.expires_at:
            del self._cache[key]
            self._logger.debug("Configuration cache entry expired", key=key)
            return None

        self.cache_hits += 1
        self._logger.debug("Configuration cache hit", key=key)
        return entry.value

    def _put_in_cache(self, key: str, value: ConfigurationValue) -> None:
        """
        Store configuration in cache.

        Args:
            key: Configuration key
            value: Configuration value to cache
        """
        expires_at = datetime.utcnow() + timedelta(seconds=self._cache_ttl)
        self._cache[key] = _CacheEntry(value=value, expires_at=expires_at)
        self._logger.debug("Configuration cached", key=key, expires_at=expires_at)

    async def get_configuration(self, key: str) -> ConfigurationValue:
        """
        Get configuration value by key.

        Args:
            key: Configuration key

        Returns:
            Configuration value

        Raises:
            ConfigurationError: If configuration not found or service error
        """
        # Check cache first
        cached_value = self._get_from_cache(key)
        if cached_value:
            return cached_value

        # Cache miss - fetch from service
        self._cache_misses += 1

        try:
            endpoint = await self._get_service_endpoint()
            url = f"{endpoint}/api/v1/configuration/{key}"

            client = await self._get_client()

            self._logger.debug("Fetching configuration from service", key=key, url=url)

            response = await client.get(url)

            if response.status_code == 404:
                raise ConfigurationError(
                    f"Configuration not found: {key}",
                    key=key,
                    status_code=404
                )
            elif response.status_code != 200:
                error_text = response.text
                raise ConfigurationError(
                    f"Configuration service error: HTTP {response.status_code}: {error_text}",
                    key=key,
                    status_code=response.status_code
                )

            data = response.json()

            # Create configuration value
            config_value = ConfigurationValue(
                key=data["key"],
                value=data["value"],
                type=data["type"],
                environment=data.get("environment", "production")
            )

            # Validate before caching
            config_value.validate()

            # Cache the value
            self._put_in_cache(key, config_value)

            self._logger.info(
                "Configuration retrieved successfully",
                key=key,
                type=config_value.type,
                environment=config_value.environment
            )

            return config_value

        except (asyncio.TimeoutError, httpx.TimeoutException):
            raise ConfigurationError(
                f"Configuration service timeout for key: {key}",
                key=key
            )
        except httpx.RequestError as e:
            raise ConfigurationError(
                f"Configuration service client error for key {key}: {e}",
                key=key
            )
        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise ConfigurationError(
                f"Unexpected error retrieving configuration {key}: {e}",
                key=key
            )

    def get_cache_stats(self) -> Dict[str, Union[int, float]]:
        """
        Get cache statistics.

        Returns:
            Dictionary containing cache statistics
        """
        total_requests = self.cache_hits + self._cache_misses
        hit_rate = self.cache_hits / total_requests if total_requests > 0 else 0.0

        return {
            "cache_size": len(self._cache),
            "cache_hits": self.cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": hit_rate,
            "total_requests": total_requests
        }

    async def cleanup(self) -> None:
        """Clean up resources."""
        self._logger.info("Cleaning up configuration client")

        # Clear cache
        self._cache.clear()
        self.cache_hits = 0
        self._cache_misses = 0

        # Close HTTP client
        if self._client:
            await self._client.aclose()
            self._client = None

        self._logger.info("Configuration client cleanup completed")

    def __repr__(self) -> str:
        """String representation."""
        cache_stats = self.get_cache_stats()
        return (
            f"ConfigurationServiceClient("
            f"environment={self.settings.environment}, "
            f"cache_size={cache_stats['cache_size']}, "
            f"hit_rate={cache_stats['hit_rate']:.2f})"
        )