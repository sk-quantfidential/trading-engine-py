#!/usr/bin/env python3
"""
Integration tests for Configuration Service Client

This module contains comprehensive failing tests for TSE-0001.3c Task 1 (TDD RED phase).
These tests define the expected behavior of the ConfigurationServiceClient and
ConfigurationValue classes before implementation.

🎯 Test Coverage:
- ConfigurationServiceClient lifecycle management
- ConfigurationValue validation and type conversion
- Service discovery integration
- Cache management and statistics
- Error handling for various failure scenarios
- Environment-specific configuration support
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Optional, Dict, Any
import time

# These imports will fail initially (TDD RED phase)
from trading_system.infrastructure.config import Settings
from trading_system.infrastructure.configuration_client import (
    ConfigurationServiceClient,
    ConfigurationValue,
    ConfigurationError,
    DEFAULT_CACHE_TTL_SECONDS,
    VALID_CONFIG_TYPES
)
from trading_system.infrastructure.service_discovery import ServiceDiscovery, ServiceInfo


class TestConfigurationValue:
    """Test ConfigurationValue data model and validation."""

    def test_configuration_value_creation(self):
        """Test basic ConfigurationValue creation."""
        config = ConfigurationValue(
            key="trading.position_limits.max_size",
            value="1000000",
            type="number"
        )

        assert config.key == "trading.position_limits.max_size"
        assert config.value == "1000000"
        assert config.type == "number"
        assert config.environment == "production"  # default

    def test_configuration_value_with_environment(self):
        """Test ConfigurationValue with specific environment."""
        config = ConfigurationValue(
            key="trading.risk_limits.max_drawdown",
            value="0.05",
            type="number",
            environment="testing"
        )

        assert config.environment == "testing"

    def test_configuration_value_validation_valid_types(self):
        """Test ConfigurationValue validation for valid types."""
        valid_configs = [
            ConfigurationValue(key="app.name", value="trading-engine", type="string"),
            ConfigurationValue(key="app.port", value="8080", type="number"),
            ConfigurationValue(key="app.enabled", value="true", type="boolean"),
            ConfigurationValue(key="app.config", value='{"key": "value"}', type="json")
        ]

        for config in valid_configs:
            assert config.validate() is True

    def test_configuration_value_validation_invalid_types(self):
        """Test ConfigurationValue validation for invalid types."""
        with pytest.raises(ValueError, match="Invalid configuration type"):
            ConfigurationValue(
                key="app.invalid",
                value="value",
                type="invalid_type"
            )

    def test_configuration_value_type_conversions(self):
        """Test ConfigurationValue type conversion methods."""
        # String conversion
        string_config = ConfigurationValue(
            key="app.name",
            value="trading-engine",
            type="string"
        )
        assert string_config.as_string() == "trading-engine"

        # Number conversion
        number_config = ConfigurationValue(
            key="app.max_position",
            value="1000000.50",
            type="number"
        )
        assert number_config.as_float() == 1000000.50
        assert number_config.as_int() == 1000000

        # Boolean conversion
        bool_config = ConfigurationValue(
            key="app.enabled",
            value="true",
            type="boolean"
        )
        assert bool_config.as_bool() is True

        # JSON conversion
        json_config = ConfigurationValue(
            key="app.settings",
            value='{"timeout": 30, "retries": 3}',
            type="json"
        )
        parsed = json_config.as_json()
        assert parsed["timeout"] == 30
        assert parsed["retries"] == 3

    def test_configuration_value_invalid_conversions(self):
        """Test ConfigurationValue invalid type conversions."""
        config = ConfigurationValue(
            key="app.invalid",
            value="not_a_number",
            type="number"
        )

        with pytest.raises(ValueError):
            config.as_float()

        with pytest.raises(ValueError):
            config.as_int()

    def test_configuration_value_constants(self):
        """Test ConfigurationValue related constants."""
        assert DEFAULT_CACHE_TTL_SECONDS == 300  # 5 minutes
        assert "string" in VALID_CONFIG_TYPES
        assert "number" in VALID_CONFIG_TYPES
        assert "boolean" in VALID_CONFIG_TYPES
        assert "json" in VALID_CONFIG_TYPES
        assert len(VALID_CONFIG_TYPES) == 4


class TestConfigurationServiceClient:
    """Test ConfigurationServiceClient functionality."""

    @pytest.fixture
    def settings(self):
        """Create Settings instance for testing."""
        return Settings(environment="testing")

    @pytest.fixture
    def mock_service_discovery(self):
        """Create mock ServiceDiscovery instance."""
        mock_discovery = Mock(spec=ServiceDiscovery)
        mock_service_info = ServiceInfo(
            name="configuration-service",
            version="1.0.0",
            host="localhost",
            http_port=8080,
            grpc_port=50051,
            status="healthy"
        )
        mock_discovery.get_service = AsyncMock(return_value=mock_service_info)
        return mock_discovery

    @pytest.fixture
    def client(self, settings, mock_service_discovery):
        """Create ConfigurationServiceClient instance for testing."""
        return ConfigurationServiceClient(
            settings=settings,
            service_discovery=mock_service_discovery
        )

    def test_configuration_client_initialization(self, settings):
        """Test ConfigurationServiceClient basic initialization."""
        client = ConfigurationServiceClient(settings)

        assert client.settings == settings
        assert client.service_discovery is None
        assert client._cache == {}
        assert client.cache_hits == 0
        assert client._cache_misses == 0

    def test_configuration_client_with_service_discovery(self, settings, mock_service_discovery):
        """Test ConfigurationServiceClient with service discovery."""
        client = ConfigurationServiceClient(
            settings=settings,
            service_discovery=mock_service_discovery
        )

        assert client.service_discovery == mock_service_discovery

    @pytest.mark.asyncio
    async def test_get_service_endpoint_with_discovery(self, client, mock_service_discovery):
        """Test service endpoint resolution with service discovery."""
        endpoint = await client._get_service_endpoint()

        assert endpoint == "http://localhost:8080"
        mock_service_discovery.get_service.assert_called_once_with("configuration-service")

    @pytest.mark.asyncio
    async def test_get_service_endpoint_fallback(self, settings):
        """Test service endpoint fallback when no service discovery."""
        client = ConfigurationServiceClient(settings)
        endpoint = await client._get_service_endpoint()

        # Should fall back to default configuration service endpoint
        assert endpoint == "http://localhost:8090"  # Default config service port

    @pytest.mark.asyncio
    async def test_get_configuration_success(self, client):
        """Test successful configuration retrieval."""
        # Mock HTTP response
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "key": "trading.position_limits.max_size",
                "value": "1000000",
                "type": "number",
                "environment": "testing"
            }
            mock_get.return_value = mock_response

            config = await client.get_configuration("trading.position_limits.max_size")

            assert isinstance(config, ConfigurationValue)
            assert config.key == "trading.position_limits.max_size"
            assert config.value == "1000000"
            assert config.type == "number"

    @pytest.mark.asyncio
    async def test_get_configuration_not_found(self, client):
        """Test configuration retrieval when key not found."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            with pytest.raises(ConfigurationError, match="Configuration not found"):
                await client.get_configuration("nonexistent.key")

    @pytest.mark.asyncio
    async def test_get_configuration_service_error(self, client):
        """Test configuration retrieval with service error."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_get.return_value = mock_response

            with pytest.raises(ConfigurationError, match="Configuration service error"):
                await client.get_configuration("some.key")

    @pytest.mark.asyncio
    async def test_configuration_caching(self, client):
        """Test configuration caching functionality."""
        # Mock successful HTTP response
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "key": "trading.cache_test",
                "value": "cached_value",
                "type": "string",
                "environment": "testing"
            }
            mock_get.return_value = mock_response

            # First call should hit the service
            config1 = await client.get_configuration("trading.cache_test")
            assert mock_get.call_count == 1
            assert client.cache_hits == 0
            assert client._cache_misses == 1

            # Second call should hit the cache
            config2 = await client.get_configuration("trading.cache_test")
            assert mock_get.call_count == 1  # No additional HTTP calls
            assert client.cache_hits == 1
            assert client._cache_misses == 1

            # Both configs should be identical
            assert config1.key == config2.key
            assert config1.value == config2.value

    def test_cache_statistics(self, client):
        """Test cache statistics functionality."""
        # Initially empty cache
        stats = client.get_cache_stats()
        expected_stats = {
            "cache_size": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "hit_rate": 0.0,
            "total_requests": 0
        }
        assert stats == expected_stats

        # Simulate some cache activity
        client.cache_hits = 7
        client._cache_misses = 3
        client._cache = {"key1": "value1", "key2": "value2"}

        stats = client.get_cache_stats()
        expected_stats = {
            "cache_size": 2,
            "cache_hits": 7,
            "cache_misses": 3,
            "hit_rate": 0.7,  # 7/10
            "total_requests": 10
        }
        assert stats == expected_stats

    @pytest.mark.asyncio
    async def test_cache_expiration(self, client):
        """Test cache expiration functionality."""
        # Mock the cache TTL to be very short for testing
        with patch.object(client, '_cache_ttl', 0.1):  # 100ms TTL
            with patch('httpx.AsyncClient.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "key": "trading.ttl_test",
                    "value": "initial_value",
                    "type": "string",
                    "environment": "testing"
                }
                mock_get.return_value = mock_response

                # First call
                config1 = await client.get_configuration("trading.ttl_test")
                assert config1.value == "initial_value"
                assert mock_get.call_count == 1

                # Wait for cache to expire
                await asyncio.sleep(0.2)

                # Update mock to return different value
                mock_response.json.return_value = {
                    "key": "trading.ttl_test",
                    "value": "updated_value",
                    "type": "string",
                    "environment": "testing"
                }

                # Second call should fetch fresh data
                config2 = await client.get_configuration("trading.ttl_test")
                assert config2.value == "updated_value"
                assert mock_get.call_count == 2

    @pytest.mark.asyncio
    async def test_configuration_timeout_handling(self, client):
        """Test configuration retrieval timeout handling."""
        with patch('httpx.AsyncClient.get') as mock_get:
            # Simulate timeout
            import httpx
            mock_get.side_effect = httpx.TimeoutException("Request timeout")

            with pytest.raises(ConfigurationError, match="Configuration service timeout"):
                await client.get_configuration("timeout.test")

    def test_environment_validation(self, mock_service_discovery):
        """Test environment validation in Settings."""
        # Valid environment
        settings = Settings(environment="testing")
        client = ConfigurationServiceClient(settings, mock_service_discovery)
        assert client.settings.environment == "testing"

        # Invalid environment should raise validation error
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            Settings(environment="invalid_env")

    @pytest.mark.asyncio
    async def test_concurrent_configuration_requests(self, client):
        """Test handling of concurrent configuration requests."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "key": "trading.concurrent_test",
                "value": "concurrent_value",
                "type": "string",
                "environment": "testing"
            }
            mock_get.return_value = mock_response

            # Make multiple concurrent requests for the same key
            tasks = [
                client.get_configuration("trading.concurrent_test")
                for _ in range(5)
            ]

            results = await asyncio.gather(*tasks)

            # All should return the same configuration
            for result in results:
                assert result.value == "concurrent_value"

            # Should have made only one HTTP request due to caching
            assert mock_get.call_count == 1

    @pytest.mark.asyncio
    async def test_configuration_client_cleanup(self, client):
        """Test ConfigurationServiceClient cleanup."""
        # Add some data to cache
        client._cache["test.key"] = "test.value"
        client.cache_hits = 5
        client._cache_misses = 2

        # Cleanup should clear cache and reset stats
        await client.cleanup()

        assert client._cache == {}
        assert client.cache_hits == 0
        assert client._cache_misses == 0

    def test_configuration_error_types(self):
        """Test ConfigurationError exception types."""
        # Test basic ConfigurationError
        error = ConfigurationError("Test error message")
        assert str(error) == "Test error message"

        # Test ConfigurationError with key context
        error_with_key = ConfigurationError("Not found", key="missing.key")
        assert "missing.key" in str(error_with_key)