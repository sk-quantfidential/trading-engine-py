#!/usr/bin/env python3
"""
Integration tests for Inter-Service Communication

This module contains comprehensive failing tests for TSE-0001.3c Task 3 (TDD RED phase).
These tests define the expected behavior of the InterServiceClientManager and
related gRPC client classes before implementation.

🎯 Test Coverage:
- InterServiceClientManager lifecycle and connection management
- RiskMonitorClient and TestCoordinatorClient gRPC communication
- Service discovery integration for dynamic endpoint resolution
- Circuit breaker patterns for resilient communication
- OpenTelemetry tracing and performance monitoring
- Error handling and timeout management
- Connection pooling and resource management
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Optional, Dict, Any, List
import time
import grpc

# These imports will fail initially (TDD RED phase)
from trading_system.infrastructure.config import Settings
from trading_system.infrastructure.grpc_clients import (
    InterServiceClientManager,
    RiskMonitorClient,
    TestCoordinatorClient,
    ServiceCommunicationError,
    DEFAULT_GRPC_TIMEOUT,
    DEFAULT_RISK_MONITOR_PORT,
    DEFAULT_TEST_COORDINATOR_PORT
)
from trading_system.infrastructure.service_discovery import ServiceDiscovery, ServiceInfo

# Data models for inter-service communication (will be implemented)
from trading_system.infrastructure.grpc_clients import (
    StrategyStatus,
    Position,
    ScenarioStatus,
    ChaosEvent,
    HealthResponse
)


class TestInterServiceClientManager:
    """Test InterServiceClientManager functionality."""

    @pytest.fixture
    def settings(self):
        """Create Settings instance for testing."""
        return Settings(environment="testing")

    @pytest.fixture
    def mock_service_discovery(self):
        """Create mock ServiceDiscovery instance."""
        mock_discovery = Mock(spec=ServiceDiscovery)

        # Mock risk monitor service info
        risk_monitor_info = ServiceInfo(
            name="risk-monitor",
            version="1.0.0",
            host="localhost",
            http_port=8084,
            grpc_port=50054,
            status="healthy"
        )

        # Mock test coordinator service info
        test_coordinator_info = ServiceInfo(
            name="test-coordinator",
            version="1.0.0",
            host="localhost",
            http_port=8083,
            grpc_port=50053,
            status="healthy"
        )

        # Configure mock to return different services
        def mock_get_service(service_name):
            if service_name == "risk-monitor":
                return AsyncMock(return_value=risk_monitor_info)()
            elif service_name == "test-coordinator":
                return AsyncMock(return_value=test_coordinator_info)()
            else:
                return AsyncMock(return_value=None)()

        mock_discovery.get_service = mock_get_service
        return mock_discovery

    @pytest.fixture
    def manager(self, settings, mock_service_discovery):
        """Create InterServiceClientManager instance for testing."""
        return InterServiceClientManager(
            settings=settings,
            service_discovery=mock_service_discovery
        )

    def test_manager_initialization(self, settings):
        """Test InterServiceClientManager basic initialization."""
        manager = InterServiceClientManager(settings)

        assert manager.settings == settings
        assert manager.service_discovery is None
        assert manager._clients == {}
        assert manager._initialized is False

    def test_manager_with_service_discovery(self, settings, mock_service_discovery):
        """Test InterServiceClientManager with service discovery."""
        manager = InterServiceClientManager(
            settings=settings,
            service_discovery=mock_service_discovery
        )

        assert manager.service_discovery == mock_service_discovery

    @pytest.mark.asyncio
    async def test_manager_initialization_lifecycle(self, manager):
        """Test manager initialization lifecycle."""
        # Initially not initialized
        assert manager._initialized is False

        # Initialize
        await manager.initialize()
        assert manager._initialized is True

        # Multiple initializations should be safe
        await manager.initialize()
        assert manager._initialized is True

    def test_manager_constants(self):
        """Test InterServiceClientManager related constants."""
        assert DEFAULT_GRPC_TIMEOUT == 30.0  # 30 seconds
        assert DEFAULT_RISK_MONITOR_PORT == 50054
        assert DEFAULT_TEST_COORDINATOR_PORT == 50053

    @pytest.mark.asyncio
    async def test_get_risk_monitor_client_with_discovery(self, manager, mock_service_discovery):
        """Test RiskMonitorClient creation with service discovery."""
        await manager.initialize()

        client = await manager.get_risk_monitor_client()

        assert isinstance(client, RiskMonitorClient)
        assert client.host == "localhost"
        assert client.port == 50054

    @pytest.mark.asyncio
    async def test_get_risk_monitor_client_fallback(self, settings):
        """Test RiskMonitorClient creation with fallback when no service discovery."""
        manager = InterServiceClientManager(settings)
        await manager.initialize()

        client = await manager.get_risk_monitor_client(use_fallback=True)

        assert isinstance(client, RiskMonitorClient)
        assert client.host == "localhost"
        assert client.port == DEFAULT_RISK_MONITOR_PORT

    @pytest.mark.asyncio
    async def test_get_test_coordinator_client_with_discovery(self, manager, mock_service_discovery):
        """Test TestCoordinatorClient creation with service discovery."""
        await manager.initialize()

        client = await manager.get_test_coordinator_client()

        assert isinstance(client, TestCoordinatorClient)
        assert client.host == "localhost"
        assert client.port == 50053

    @pytest.mark.asyncio
    async def test_get_test_coordinator_client_fallback(self, settings):
        """Test TestCoordinatorClient creation with fallback when no service discovery."""
        manager = InterServiceClientManager(settings)
        await manager.initialize()

        client = await manager.get_test_coordinator_client(use_fallback=True)

        assert isinstance(client, TestCoordinatorClient)
        assert client.host == "localhost"
        assert client.port == DEFAULT_TEST_COORDINATOR_PORT

    def test_manager_statistics(self, manager):
        """Test manager statistics functionality."""
        # Initially empty stats
        stats = manager.get_manager_stats()
        expected_stats = {
            "total_clients": 0,
            "active_connections": 0,
            "initialized": False,
            "service_discovery_enabled": True,
            "client_types": []
        }
        assert stats == expected_stats

        # After adding clients (simulate)
        manager._clients = {
            "risk-monitor": Mock(spec=RiskMonitorClient),
            "test-coordinator": Mock(spec=TestCoordinatorClient)
        }
        manager._initialized = True

        stats = manager.get_manager_stats()
        expected_stats = {
            "total_clients": 2,
            "active_connections": 2,
            "initialized": True,
            "service_discovery_enabled": True,
            "client_types": ["risk-monitor", "test-coordinator"]
        }
        assert stats == expected_stats

    @pytest.mark.asyncio
    async def test_client_caching(self, manager):
        """Test client caching functionality."""
        await manager.initialize()

        # First call should create new client
        client1 = await manager.get_risk_monitor_client(use_fallback=True)
        assert "risk-monitor" in manager._clients

        # Second call should return cached client
        client2 = await manager.get_risk_monitor_client(use_fallback=True)
        assert client1 is client2

    @pytest.mark.asyncio
    async def test_manager_cleanup(self, manager):
        """Test InterServiceClientManager cleanup."""
        await manager.initialize()

        # Add some clients
        await manager.get_risk_monitor_client(use_fallback=True)
        await manager.get_test_coordinator_client(use_fallback=True)

        assert len(manager._clients) > 0
        assert manager._initialized is True

        # Cleanup should close all clients and reset state
        await manager.cleanup()

        assert len(manager._clients) == 0
        assert manager._initialized is False

    @pytest.mark.asyncio
    async def test_service_discovery_failure_handling(self, settings):
        """Test handling of service discovery failures."""
        # Mock service discovery that fails
        mock_discovery = Mock(spec=ServiceDiscovery)
        mock_discovery.get_service = AsyncMock(side_effect=Exception("Service discovery failed"))

        manager = InterServiceClientManager(settings, mock_discovery)
        await manager.initialize()

        # Should fall back to default when service discovery fails
        client = await manager.get_risk_monitor_client(use_fallback=True)
        assert isinstance(client, RiskMonitorClient)
        assert client.port == DEFAULT_RISK_MONITOR_PORT


class TestRiskMonitorClient:
    """Test RiskMonitorClient functionality."""

    @pytest.fixture
    def settings(self):
        """Create Settings instance for testing."""
        return Settings(environment="testing")

    @pytest.fixture
    def client(self, settings):
        """Create RiskMonitorClient instance for testing."""
        return RiskMonitorClient(
            host="localhost",
            port=50054,
            settings=settings
        )

    def test_risk_monitor_client_initialization(self, settings):
        """Test RiskMonitorClient basic initialization."""
        client = RiskMonitorClient(
            host="localhost",
            port=50054,
            settings=settings
        )

        assert client.host == "localhost"
        assert client.port == 50054
        assert client.settings == settings
        assert client._channel is None
        assert client._stub is None

    @pytest.mark.asyncio
    async def test_risk_monitor_client_connection(self, client):
        """Test RiskMonitorClient connection establishment."""
        # Mock gRPC channel and stub
        with patch('grpc.aio.insecure_channel') as mock_channel:
            mock_channel_instance = AsyncMock()
            mock_channel.return_value = mock_channel_instance

            await client.connect()

            assert client._channel is not None
            mock_channel.assert_called_once_with("localhost:50054")

    @pytest.mark.asyncio
    async def test_risk_monitor_health_check(self, client):
        """Test RiskMonitorClient health check."""
        # Mock the stub and its methods
        with patch.object(client, '_stub') as mock_stub:
            mock_stub.health_check = AsyncMock()

            # Mock successful health check
            with patch.object(client, '_make_request') as mock_request:
                mock_request.return_value = HealthResponse(
                    status="SERVING",
                    service="risk-monitor"
                )

                response = await client.health_check()

                assert isinstance(response, HealthResponse)
                assert response.status == "SERVING"
                assert response.service == "risk-monitor"

    @pytest.mark.asyncio
    async def test_submit_strategy_status(self, client):
        """Test submitting strategy status to risk monitor."""
        # Mock the stub and its methods
        with patch.object(client, '_stub') as mock_stub:
            mock_stub.submit_strategy_status = AsyncMock()

            strategy_status = StrategyStatus(
                strategy_id="market_making_001",
                status="ACTIVE",
                positions=[
                    Position(
                        instrument_id="BTC/USD",
                        quantity=0.5,
                        value=25000.0,
                        side="LONG"
                    )
                ],
                last_updated=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            )

            # Mock successful submission
            with patch.object(client, '_make_request') as mock_request:
                mock_request.return_value = {"success": True, "message": "Status received"}

                response = await client.submit_strategy_status(strategy_status)

                assert response["success"] is True
                mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_risk_monitor_client_error_handling(self, client):
        """Test RiskMonitorClient error handling."""
        # Mock the stub and its methods
        with patch.object(client, '_stub') as mock_stub:
            mock_stub.health_check = AsyncMock()

            # Mock gRPC error conversion to ServiceCommunicationError
            with patch.object(client, '_make_request') as mock_request:
                mock_request.side_effect = ServiceCommunicationError("Connection failed")

                with pytest.raises(ServiceCommunicationError, match="Connection failed"):
                    await client.health_check()

    def test_risk_monitor_client_statistics(self, client):
        """Test RiskMonitorClient statistics tracking."""
        stats = client.get_stats()
        expected_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "last_request_time": None,
            "connection_status": "disconnected"
        }
        assert stats == expected_stats

        # Simulate some activity
        client._total_requests = 10
        client._successful_requests = 8
        client._failed_requests = 2
        client._last_request_time = time.time()

        stats = client.get_stats()
        assert stats["total_requests"] == 10
        assert stats["successful_requests"] == 8
        assert stats["failed_requests"] == 2
        assert stats["last_request_time"] is not None

    @pytest.mark.asyncio
    async def test_risk_monitor_client_cleanup(self, client):
        """Test RiskMonitorClient cleanup."""
        # Mock connected state
        client._channel = AsyncMock()
        client._stub = Mock()

        await client.cleanup()

        client._channel.close.assert_called_once()
        assert client._channel is None
        assert client._stub is None


class TestTestCoordinatorClient:
    """Test TestCoordinatorClient functionality."""

    @pytest.fixture
    def settings(self):
        """Create Settings instance for testing."""
        return Settings(environment="testing")

    @pytest.fixture
    def client(self, settings):
        """Create TestCoordinatorClient instance for testing."""
        return TestCoordinatorClient(
            host="localhost",
            port=50053,
            settings=settings
        )

    def test_test_coordinator_client_initialization(self, settings):
        """Test TestCoordinatorClient basic initialization."""
        client = TestCoordinatorClient(
            host="localhost",
            port=50053,
            settings=settings
        )

        assert client.host == "localhost"
        assert client.port == 50053
        assert client.settings == settings

    @pytest.mark.asyncio
    async def test_test_coordinator_health_check(self, client):
        """Test TestCoordinatorClient health check."""
        # Mock the stub and its methods
        with patch.object(client, '_stub') as mock_stub:
            mock_stub.health_check = AsyncMock()

            # Mock successful health check
            with patch.object(client, '_make_request') as mock_request:
                mock_request.return_value = HealthResponse(
                    status="SERVING",
                    service="test-coordinator"
                )

                response = await client.health_check()

                assert isinstance(response, HealthResponse)
                assert response.status == "SERVING"
                assert response.service == "test-coordinator"

    @pytest.mark.asyncio
    async def test_submit_scenario_status(self, client):
        """Test submitting scenario status to test coordinator."""
        scenario_status = ScenarioStatus(
            scenario_id="chaos_test_001",
            status="RUNNING",
            start_time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )

        # Mock successful submission
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = {"success": True, "scenario_id": "chaos_test_001"}

            response = await client.submit_scenario_status(scenario_status)

            assert response["success"] is True
            assert response["scenario_id"] == "chaos_test_001"

    @pytest.mark.asyncio
    async def test_report_chaos_event(self, client):
        """Test reporting chaos events to test coordinator."""
        chaos_event = ChaosEvent(
            event_type="service_restart",
            target_service="trading-engine",
            event_id="chaos_123",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )

        # Mock successful submission
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = {"acknowledged": True, "event_id": "chaos_123"}

            response = await client.report_chaos_event(chaos_event)

            assert response["acknowledged"] is True
            assert response["event_id"] == "chaos_123"


class TestDataModels:
    """Test data model classes for inter-service communication."""

    def test_strategy_status_creation(self):
        """Test StrategyStatus data model."""
        positions = [
            Position(
                instrument_id="BTC/USD",
                quantity=1.0,
                value=50000.0,
                side="LONG"
            ),
            Position(
                instrument_id="ETH/USD",
                quantity=10.0,
                value=30000.0,
                side="LONG"
            )
        ]

        strategy = StrategyStatus(
            strategy_id="arbitrage_001",
            status="ACTIVE",
            positions=positions,
            last_updated=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )

        assert strategy.strategy_id == "arbitrage_001"
        assert strategy.status == "ACTIVE"
        assert len(strategy.positions) == 2
        assert strategy.positions[0].instrument_id == "BTC/USD"

    def test_position_creation(self):
        """Test Position data model."""
        position = Position(
            instrument_id="BTC/USD",
            quantity=0.5,
            value=25000.0,
            side="LONG"
        )

        assert position.instrument_id == "BTC/USD"
        assert position.quantity == 0.5
        assert position.value == 25000.0
        assert position.side == "LONG"

    def test_scenario_status_creation(self):
        """Test ScenarioStatus data model."""
        scenario = ScenarioStatus(
            scenario_id="load_test_001",
            status="RUNNING",
            start_time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )

        assert scenario.scenario_id == "load_test_001"
        assert scenario.status == "RUNNING"
        assert scenario.start_time is not None

    def test_chaos_event_creation(self):
        """Test ChaosEvent data model."""
        event = ChaosEvent(
            event_type="network_partition",
            target_service="risk-monitor",
            event_id="chaos_456",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )

        assert event.event_type == "network_partition"
        assert event.target_service == "risk-monitor"
        assert event.event_id == "chaos_456"

    def test_health_response_creation(self):
        """Test HealthResponse data model."""
        health = HealthResponse(
            status="SERVING",
            service="trading-engine"
        )

        assert health.status == "SERVING"
        assert health.service == "trading-engine"


class TestCircuitBreakerPattern:
    """Test circuit breaker pattern implementation."""

    @pytest.fixture
    def settings(self):
        """Create Settings instance for testing."""
        return Settings(environment="testing")

    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_state(self, settings):
        """Test circuit breaker in closed state (normal operation)."""
        manager = InterServiceClientManager(settings)
        await manager.initialize()

        # In closed state, requests should go through
        with patch.object(manager, '_make_service_call') as mock_call:
            mock_call.return_value = {"success": True}

            client = await manager.get_risk_monitor_client(use_fallback=True)
            # Circuit breaker should allow calls through
            assert client is not None

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_state(self, settings):
        """Test circuit breaker in open state (failing fast)."""
        manager = InterServiceClientManager(settings)
        await manager.initialize()

        # Simulate multiple failures to trip the circuit breaker
        client = await manager.get_risk_monitor_client(use_fallback=True)

        # Mock consecutive failures
        with patch.object(client, '_make_request') as mock_request:
            mock_request.side_effect = ServiceCommunicationError("Service unavailable")

            # Multiple failures should trip the circuit breaker
            for _ in range(5):
                try:
                    await client.health_check()
                except ServiceCommunicationError:
                    pass

            # Circuit breaker should now be open and fail fast
            with pytest.raises(ServiceCommunicationError, match="Circuit breaker open"):
                await client.health_check()

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_state(self, settings):
        """Test circuit breaker in half-open state (testing recovery)."""
        manager = InterServiceClientManager(settings)
        await manager.initialize()
        client = await manager.get_risk_monitor_client(use_fallback=True)

        # Simulate circuit breaker in half-open state
        with patch.object(client, '_circuit_breaker_state', 'half_open'):
            with patch.object(client, '_make_request') as mock_request:
                mock_request.return_value = HealthResponse(status="SERVING", service="risk-monitor")

                # Successful call should close the circuit breaker
                response = await client.health_check()
                assert response.status == "SERVING"


class TestOpenTelemetryIntegration:
    """Test OpenTelemetry tracing integration."""

    @pytest.fixture
    def settings(self):
        """Create Settings instance for testing."""
        return Settings(environment="testing")

    @pytest.mark.asyncio
    async def test_tracing_context_propagation(self, settings):
        """Test OpenTelemetry context propagation."""
        manager = InterServiceClientManager(settings)
        await manager.initialize()

        # Mock tracing context
        with patch('opentelemetry.trace.set_span_in_context') as mock_set_span:
            with patch('opentelemetry.trace.get_current_span') as mock_get_span:
                mock_span = Mock()
                mock_get_span.return_value = mock_span

                client = await manager.get_risk_monitor_client(use_fallback=True)

                # Tracing should be set up for inter-service calls
                assert client is not None

    @pytest.mark.asyncio
    async def test_span_creation_for_service_calls(self, settings):
        """Test span creation for individual service calls."""
        client = RiskMonitorClient(
            host="localhost",
            port=50054,
            settings=settings
        )

        with patch('opentelemetry.trace.get_tracer') as mock_get_tracer:
            mock_tracer = Mock()
            mock_span = Mock()
            mock_tracer.start_span.return_value.__enter__.return_value = mock_span
            mock_get_tracer.return_value = mock_tracer

            with patch.object(client, '_make_request') as mock_request:
                mock_request.return_value = HealthResponse(status="SERVING", service="risk-monitor")

                await client.health_check()

                # Span should be created for the service call
                mock_tracer.start_span.assert_called()


class TestErrorHandlingAndResilience:
    """Test comprehensive error handling and resilience patterns."""

    @pytest.fixture
    def settings(self):
        """Create Settings instance for testing."""
        return Settings(environment="testing")

    @pytest.mark.asyncio
    async def test_timeout_handling(self, settings):
        """Test timeout handling for service calls."""
        client = RiskMonitorClient(
            host="localhost",
            port=50054,
            settings=settings,
            timeout=1.0  # 1 second timeout
        )

        with patch.object(client, '_make_request') as mock_request:
            mock_request.side_effect = asyncio.TimeoutError()

            with pytest.raises(ServiceCommunicationError, match="timeout"):
                await client.health_check()

    @pytest.mark.asyncio
    async def test_retry_mechanism(self, settings):
        """Test retry mechanism for transient failures."""
        client = RiskMonitorClient(
            host="localhost",
            port=50054,
            settings=settings
        )

        call_count = 0
        def mock_request_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise grpc.RpcError("Transient failure")
            return HealthResponse(status="SERVING", service="risk-monitor")

        with patch.object(client, '_make_request', side_effect=mock_request_side_effect):
            response = await client.health_check()
            assert response.status == "SERVING"
            assert call_count == 3  # Should have retried twice

    @pytest.mark.asyncio
    async def test_connection_recovery(self, settings):
        """Test automatic connection recovery after failures."""
        manager = InterServiceClientManager(settings)
        await manager.initialize()

        client = await manager.get_risk_monitor_client(use_fallback=True)

        # Simulate connection failure
        client._channel = None
        client._stub = None

        # Client should automatically reconnect
        with patch.object(client, 'connect') as mock_connect:
            mock_connect.return_value = None

            with patch.object(client, '_make_request') as mock_request:
                mock_request.return_value = HealthResponse(status="SERVING", service="risk-monitor")

                response = await client.health_check()
                assert response.status == "SERVING"
                mock_connect.assert_called_once()

    def test_service_communication_error_types(self):
        """Test ServiceCommunicationError exception types."""
        # Test basic ServiceCommunicationError
        error = ServiceCommunicationError("Test error message")
        assert str(error) == "Test error message"

        # Test ServiceCommunicationError with service context
        error_with_service = ServiceCommunicationError("Connection failed", service="risk-monitor")
        assert "risk-monitor" in str(error_with_service)

        # Test ServiceCommunicationError with operation context
        error_with_operation = ServiceCommunicationError(
            "Health check failed",
            service="test-coordinator",
            operation="health_check"
        )
        assert "test-coordinator" in str(error_with_operation)
        assert "health_check" in str(error_with_operation)