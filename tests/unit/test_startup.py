"""Tests for Trading System Engine startup behavior and instance awareness.

This test suite validates that the trading-system-engine-py correctly initializes
with instance-aware configuration, enabling multi-instance deployment patterns.

Test Coverage:
- Service initialization with singleton configuration
- Service initialization with multi-instance configuration
- Instance name auto-derivation
- Logger binding with instance context
- Data adapter configuration with service identity
- Settings validation
- Environment configuration
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from trading_system.infrastructure.config import Settings, get_settings


class TestSettingsInstanceAwareness:
    """Test Settings configuration with instance awareness."""

    def test_settings_singleton_instance(self):
        """Should correctly configure singleton instance."""
        settings = Settings(
            service_name="trading-system-engine",
            service_instance_name="trading-system-engine",
        )
        assert settings.service_name == "trading-system-engine"
        assert settings.service_instance_name == "trading-system-engine"
        assert settings.environment == "development"  # default

    def test_settings_multi_instance(self):
        """Should correctly configure multi-instance deployment."""
        settings = Settings(
            service_name="trading-system-engine",
            service_instance_name="trading-system-engine-LH",
            environment="production",
        )
        assert settings.service_name == "trading-system-engine"
        assert settings.service_instance_name == "trading-system-engine-LH"
        assert settings.environment == "production"

    def test_settings_auto_derive_instance_name(self):
        """Should auto-derive instance name from service name when not provided."""
        settings = Settings(
            service_name="trading-system-engine",
            service_instance_name="",  # Empty triggers auto-derivation
        )
        assert settings.service_instance_name == "trading-system-engine"

    def test_settings_docker_environment(self):
        """Should support docker environment."""
        settings = Settings(
            service_name="trading-system-engine",
            environment="docker",
        )
        assert settings.environment == "docker"
        assert settings.service_instance_name == "trading-system-engine"

    def test_settings_log_level_normalization(self):
        """Should normalize log level to uppercase."""
        settings = Settings(
            service_name="trading-system-engine",
            log_level="info",  # lowercase
        )
        assert settings.log_level == "INFO"  # normalized to uppercase

    def test_settings_default_ports(self):
        """Should use correct default ports for Trading System Engine."""
        settings = Settings()
        assert settings.http_port == 8083  # Trading Engine HTTP port (changed from 8082)
        assert settings.grpc_port == 50053  # Trading Engine gRPC port (changed from 50052)


class TestLifespanInstanceContext:
    """Test lifespan manager with instance context."""

    @pytest.mark.asyncio
    async def test_lifespan_binds_logger_context(self):
        """Should bind instance context to logger during startup."""
        from trading_system.main import lifespan
        from fastapi import FastAPI
        import structlog

        app = FastAPI()

        with patch('trading_system.main.get_settings') as mock_get_settings:
            with patch('trading_system.main.structlog.get_logger') as mock_get_logger:
                with patch('trading_system.main.create_adapter') as mock_create_adapter:
                    # Setup mocks
                    mock_settings = Mock()
                    mock_settings.service_name = "trading-system-engine"
                    mock_settings.service_instance_name = "trading-system-engine"
                    mock_settings.environment = "testing"
                    mock_settings.version = "0.1.0"
                    mock_settings.postgres_url = "postgresql://test"
                    mock_settings.redis_url = "redis://test"
                    mock_get_settings.return_value = mock_settings

                    mock_logger = Mock()
                    mock_bound_logger = Mock()
                    mock_logger.bind.return_value = mock_bound_logger
                    mock_get_logger.return_value = mock_logger

                    mock_adapter = AsyncMock()
                    mock_adapter.connection_status = Mock(
                        postgres_connected=True,
                        redis_connected=True
                    )
                    mock_adapter.disconnect = AsyncMock()
                    mock_create_adapter.return_value = mock_adapter

                    # Execute lifespan
                    async with lifespan(app):
                        pass

                    # Verify logger binding
                    mock_logger.bind.assert_called_once_with(
                        service_name="trading-system-engine",
                        instance_name="trading-system-engine",
                        environment="testing",
                    )

    @pytest.mark.asyncio
    async def test_lifespan_configures_adapter_with_identity(self):
        """Should configure data adapter with service identity."""
        from trading_system.main import lifespan
        from fastapi import FastAPI
        from trading_data_adapter import AdapterConfig

        app = FastAPI()

        with patch('trading_system.main.get_settings') as mock_get_settings:
            with patch('trading_system.main.create_adapter') as mock_create_adapter:
                with patch('trading_system.main.structlog.get_logger'):
                    # Setup mocks
                    mock_settings = Mock()
                    mock_settings.service_name = "trading-system-engine"
                    mock_settings.service_instance_name = "trading-system-engine-Alpha"
                    mock_settings.environment = "production"
                    mock_settings.version = "0.1.0"
                    mock_settings.postgres_url = "postgresql://prod"
                    mock_settings.redis_url = "redis://prod"
                    mock_get_settings.return_value = mock_settings

                    mock_adapter = AsyncMock()
                    mock_adapter.connection_status = Mock(
                        postgres_connected=True,
                        redis_connected=True
                    )
                    mock_adapter.disconnect = AsyncMock()
                    mock_create_adapter.return_value = mock_adapter

                    # Execute lifespan
                    async with lifespan(app):
                        pass

                    # Verify adapter config
                    call_args = mock_create_adapter.call_args
                    adapter_config = call_args[0][0]

                    assert adapter_config.service_name == "trading-system-engine"
                    assert adapter_config.service_instance_name == "trading-system-engine-Alpha"
                    assert adapter_config.environment == "production"
                    assert adapter_config.postgres_url == "postgresql://prod"
                    assert adapter_config.redis_url == "redis://prod"


class TestInstanceNameValidation:
    """Test instance name validation and patterns."""

    def test_instance_name_matches_service_name_singleton(self):
        """Singleton should have matching service and instance names."""
        settings = Settings(
            service_name="trading-system-engine",
            service_instance_name="trading-system-engine",
        )
        assert settings.service_name == settings.service_instance_name

    def test_instance_name_differs_for_multi_instance(self):
        """Multi-instance should have different service and instance names."""
        settings = Settings(
            service_name="trading-system-engine",
            service_instance_name="trading-system-engine-LH",
        )
        assert settings.service_name != settings.service_instance_name
        assert settings.service_instance_name.startswith(settings.service_name)

    def test_complex_instance_names(self):
        """Should handle complex instance naming patterns."""
        settings = Settings(
            service_name="trading-system-engine",
            service_instance_name="trading-system-engine-Alpha-2",
        )
        assert settings.service_instance_name == "trading-system-engine-Alpha-2"


class TestEnvironmentConfiguration:
    """Test environment-specific configuration."""

    def test_development_environment(self):
        """Should configure development environment."""
        settings = Settings(environment="development")
        assert settings.environment == "development"
        assert not settings.debug  # default

    def test_testing_environment(self):
        """Should configure testing environment."""
        settings = Settings(environment="testing")
        assert settings.environment == "testing"

    def test_production_environment(self):
        """Should configure production environment."""
        settings = Settings(environment="production")
        assert settings.environment == "production"

    def test_docker_environment(self):
        """Should configure docker environment."""
        settings = Settings(environment="docker")
        assert settings.environment == "docker"


class TestSettingsCaching:
    """Test settings caching behavior."""

    def test_get_settings_returns_cached_instance(self):
        """Should return cached settings instance."""
        # Clear cache first
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        # Should be same instance (cached)
        assert settings1 is settings2

    def test_settings_cache_clear(self):
        """Should support cache clearing."""
        get_settings.cache_clear()
        settings1 = get_settings()

        get_settings.cache_clear()
        settings2 = get_settings()

        # Should be different instances after cache clear
        assert settings1 is not settings2


class TestTradingEngineSettings:
    """Test trading engine specific settings."""

    def test_trading_engine_defaults(self):
        """Should have correct trading engine defaults."""
        settings = Settings()
        assert settings.max_position_size == 1000000.0  # $1M
        assert settings.risk_limit_threshold == 500000.0  # $500K
        assert settings.order_timeout_seconds == 30
        assert settings.strategy_cooldown_seconds == 60

    def test_trading_engine_custom_values(self):
        """Should support custom trading engine values."""
        settings = Settings(
            max_position_size=5000000.0,
            risk_limit_threshold=2500000.0,
            order_timeout_seconds=60,
            strategy_cooldown_seconds=120,
        )
        assert settings.max_position_size == 5000000.0
        assert settings.risk_limit_threshold == 2500000.0
        assert settings.order_timeout_seconds == 60
        assert settings.strategy_cooldown_seconds == 120
