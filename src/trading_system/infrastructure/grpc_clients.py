#!/usr/bin/env python3
"""
Inter-Service gRPC Communication Clients

This module provides comprehensive gRPC client management for inter-service communication
in the trading system engine. It includes connection pooling, circuit breaker patterns,
service discovery integration, and comprehensive observability.

Key Features:
- InterServiceClientManager: Central management of all gRPC clients
- RiskMonitorClient: gRPC client for risk-monitor service communication
- CoordinatorGrpcClient: gRPC client for test-coordinator service communication
- Circuit Breaker Pattern: Resilient communication with automatic failure handling
- Service Discovery: Dynamic endpoint resolution via Redis
- OpenTelemetry Tracing: Distributed context propagation and performance monitoring
- Resource Management: Proper connection pooling and cleanup
- Data Models: Complete dataclasses for all inter-service communication types
"""

import asyncio
import grpc
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, UTC
from enum import Enum

import structlog
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from .config import Settings
from .service_discovery import ServiceDiscovery, ServiceInfo
from .performance_monitor import PerformanceMonitor
from .constants import (
    DEFAULT_GRPC_TIMEOUT,
    DEFAULT_RISK_MONITOR_PORT,
    DEFAULT_TEST_COORDINATOR_PORT,
    CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
    CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS,
    MAX_RETRY_ATTEMPTS,
    RETRY_DELAY_BASE,
    RETRY_DELAY_MAX,
    OTEL_SERVICE_NAME,
    OTEL_SPAN_ATTRIBUTES
)

logger = structlog.get_logger()
tracer = trace.get_tracer(__name__)


class ServiceCommunicationError(Exception):
    """Inter-service communication related errors."""

    def __init__(
        self,
        message: str,
        service: Optional[str] = None,
        operation: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message)
        self.service = service
        self.operation = operation
        self.original_error = original_error

    def __str__(self):
        base_message = super().__str__()
        context_parts = []
        if self.service:
            context_parts.append(f"service: {self.service}")
        if self.operation:
            context_parts.append(f"operation: {self.operation}")

        if context_parts:
            return f"{base_message} ({', '.join(context_parts)})"
        return base_message


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class Position:
    """Trading position data model."""
    instrument_id: str
    quantity: float
    value: float
    side: str  # "LONG" or "SHORT"


@dataclass
class StrategyStatus:
    """Strategy status data model for risk monitor communication."""
    strategy_id: str
    status: str  # "ACTIVE", "STOPPED", "ERROR"
    positions: List[Position] = field(default_factory=list)
    last_updated: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class ScenarioStatus:
    """Test scenario status data model for test coordinator communication."""
    scenario_id: str
    status: str  # "RUNNING", "COMPLETED", "FAILED"
    start_time: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    end_time: Optional[str] = None


@dataclass
class ChaosEvent:
    """Chaos engineering event data model."""
    event_type: str
    target_service: str
    event_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class HealthResponse:
    """Health check response data model."""
    status: str  # "SERVING", "NOT_SERVING"
    service: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics."""
    state: CircuitBreakerState
    failure_count: int
    last_failure_time: Optional[float]
    last_success_time: Optional[float]
    total_calls: int
    successful_calls: int
    failed_calls: int


class CircuitBreaker:
    """Circuit breaker implementation for resilient service communication."""

    def __init__(
        self,
        failure_threshold: int = CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        recovery_timeout: int = CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
        service_name: str = "unknown"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.service_name = service_name

        # Circuit breaker state
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.last_success_time: Optional[float] = None

        # Statistics
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0

        self._logger = logger.bind(
            component="circuit_breaker",
            service=service_name
        )

    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        self.total_calls += 1

        # Check circuit breaker state
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                self._logger.info("Circuit breaker transitioning to half-open")
            else:
                raise ServiceCommunicationError(
                    f"Circuit breaker open for service {self.service_name}",
                    service=self.service_name
                )

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        if self.last_failure_time is None:
            return False
        return time.time() - self.last_failure_time >= self.recovery_timeout

    def _on_success(self):
        """Handle successful call."""
        self.successful_calls += 1
        self.last_success_time = time.time()

        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.CLOSED
            self.failure_count = 0
            self._logger.info("Circuit breaker closed after successful recovery")

    def _on_failure(self):
        """Handle failed call."""
        self.failed_calls += 1
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            self._logger.warning(
                "Circuit breaker opened due to failures",
                failure_count=self.failure_count,
                threshold=self.failure_threshold
            )

    def get_stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics."""
        return CircuitBreakerStats(
            state=self.state,
            failure_count=self.failure_count,
            last_failure_time=self.last_failure_time,
            last_success_time=self.last_success_time,
            total_calls=self.total_calls,
            successful_calls=self.successful_calls,
            failed_calls=self.failed_calls
        )


class BaseGrpcClient:
    """Base class for all gRPC service clients."""

    def __init__(
        self,
        host: str,
        port: int,
        settings: Settings,
        timeout: float = DEFAULT_GRPC_TIMEOUT,
        service_name: str = "unknown"
    ):
        self.host = host
        self.port = port
        self.settings = settings
        self.timeout = timeout
        self.service_name = service_name

        # Connection state
        self._channel: Optional[grpc.aio.Channel] = None
        self._stub = None

        # Statistics tracking
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._last_request_time: Optional[float] = None

        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(service_name=service_name)

        # Performance monitoring
        self.performance_monitor = PerformanceMonitor(service_name=service_name)

        self._logger = logger.bind(
            component="grpc_client",
            service=service_name,
            host=host,
            port=port
        )

    @property
    def address(self) -> str:
        """Get gRPC service address."""
        return f"{self.host}:{self.port}"

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._channel is not None and self._stub is not None

    async def connect(self):
        """Establish gRPC connection."""
        if self.is_connected:
            return

        try:
            self._channel = grpc.aio.insecure_channel(self.address)
            # Create stub in subclasses
            self._create_stub()

            self._logger.info("gRPC client connected successfully")
        except Exception as e:
            self._logger.error("Failed to connect gRPC client", error=str(e))
            raise ServiceCommunicationError(
                f"Failed to connect to {self.service_name}",
                service=self.service_name,
                original_error=e
            )

    def _create_stub(self):
        """Create gRPC stub. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _create_stub")

    async def _make_request(self, operation: str, request_func, *args, **kwargs):
        """Make gRPC request with error handling and observability."""
        if not self.is_connected:
            await self.connect()

        self._total_requests += 1
        start_time = time.time()
        self._last_request_time = start_time

        # Create tracing span
        with tracer.start_as_current_span(
            f"{self.service_name}.{operation}",
            attributes={
                "service.name": self.service_name,
                "service.host": self.host,
                "service.port": self.port,
                "operation": operation
            }
        ) as span:
            try:
                # Execute request with circuit breaker protection
                result = await self.circuit_breaker.call(
                    self._execute_request, request_func, *args, **kwargs
                )

                # Record successful request in performance monitor
                duration = time.time() - start_time
                self.performance_monitor.record_request(duration, True, operation)

                self._successful_requests += 1
                span.set_status(Status(StatusCode.OK))

                self._logger.debug(
                    "gRPC request successful",
                    operation=operation,
                    duration_ms=duration * 1000
                )

                return result

            except Exception as e:
                # Record failed request in performance monitor
                duration = time.time() - start_time
                self.performance_monitor.record_request(duration, False, operation)

                self._failed_requests += 1
                span.set_status(Status(StatusCode.ERROR, str(e)))

                self._logger.error(
                    "gRPC request failed",
                    operation=operation,
                    error=str(e)
                )

                # Wrap gRPC errors
                if isinstance(e, grpc.RpcError):
                    raise ServiceCommunicationError(
                        f"gRPC call failed: {e.details()}",
                        service=self.service_name,
                        operation=operation,
                        original_error=e
                    )
                elif isinstance(e, ServiceCommunicationError):
                    raise
                else:
                    raise ServiceCommunicationError(
                        f"Unexpected error in {operation}: {e}",
                        service=self.service_name,
                        operation=operation,
                        original_error=e
                    )

    async def _execute_request(self, request_func, *args, **kwargs):
        """Execute the actual gRPC request with timeout."""
        try:
            return await asyncio.wait_for(
                request_func(*args, **kwargs),
                timeout=self.timeout
            )
        except asyncio.TimeoutError:
            raise ServiceCommunicationError(
                f"Request timeout after {self.timeout}s",
                service=self.service_name
            )

    async def health_check(self) -> HealthResponse:
        """Perform health check. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement health_check")

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive client statistics."""
        circuit_stats = self.circuit_breaker.get_stats()
        performance_metrics = self.performance_monitor.get_metrics()
        health_status = self.performance_monitor.get_health_status()

        return {
            "total_requests": self._total_requests,
            "successful_requests": self._successful_requests,
            "failed_requests": self._failed_requests,
            "last_request_time": self._last_request_time,
            "connection_status": "connected" if self.is_connected else "disconnected",
            "circuit_breaker": {
                "state": circuit_stats.state.value,
                "failure_count": circuit_stats.failure_count,
                "total_calls": circuit_stats.total_calls,
                "success_rate": (
                    circuit_stats.successful_calls / circuit_stats.total_calls
                    if circuit_stats.total_calls > 0 else 0.0
                )
            },
            "performance": {
                "average_response_time": performance_metrics.average_response_time,
                "min_response_time": performance_metrics.min_response_time,
                "max_response_time": performance_metrics.max_response_time,
                "throughput_per_second": performance_metrics.throughput_per_second
            },
            "health": health_status
        }

    async def cleanup(self):
        """Clean up gRPC client resources."""
        self._logger.info("Cleaning up gRPC client")

        if self._channel:
            await self._channel.close()
            self._channel = None
            self._stub = None

        self._logger.info("gRPC client cleanup completed")


class RiskMonitorClient(BaseGrpcClient):
    """gRPC client for risk-monitor service communication."""

    def __init__(
        self,
        host: str,
        port: int,
        settings: Settings,
        timeout: float = DEFAULT_GRPC_TIMEOUT
    ):
        super().__init__(host, port, settings, timeout, "risk-monitor")

    def _create_stub(self):
        """Create risk monitor gRPC stub."""
        # In a real implementation, this would use generated protobuf stubs
        # For now, we'll create a mock stub for testing
        self._stub = MockRiskMonitorStub(self._channel)

    async def health_check(self) -> HealthResponse:
        """Perform health check on risk monitor service."""
        return await self._make_request(
            "health_check",
            self._stub.health_check,
            {}  # Empty health check request
        )

    async def submit_strategy_status(self, strategy_status: StrategyStatus) -> Dict[str, Any]:
        """Submit strategy status to risk monitor."""
        return await self._make_request(
            "submit_strategy_status",
            self._stub.submit_strategy_status,
            strategy_status
        )

    async def get_risk_metrics(self) -> Dict[str, Any]:
        """Get current risk metrics from risk monitor."""
        return await self._make_request(
            "get_risk_metrics",
            self._stub.get_risk_metrics,
            {}
        )


class CoordinatorGrpcClient(BaseGrpcClient):
    """gRPC client for test-coordinator service communication."""

    def __init__(
        self,
        host: str,
        port: int,
        settings: Settings,
        timeout: float = DEFAULT_GRPC_TIMEOUT
    ):
        super().__init__(host, port, settings, timeout, "test-coordinator")

    def _create_stub(self):
        """Create test coordinator gRPC stub."""
        # In a real implementation, this would use generated protobuf stubs
        # For now, we'll create a mock stub for testing
        self._stub = MockTestCoordinatorStub(self._channel)

    async def health_check(self) -> HealthResponse:
        """Perform health check on test coordinator service."""
        return await self._make_request(
            "health_check",
            self._stub.health_check,
            {}  # Empty health check request
        )

    async def submit_scenario_status(self, scenario_status: ScenarioStatus) -> Dict[str, Any]:
        """Submit scenario status to test coordinator."""
        return await self._make_request(
            "submit_scenario_status",
            self._stub.submit_scenario_status,
            scenario_status
        )

    async def report_chaos_event(self, chaos_event: ChaosEvent) -> Dict[str, Any]:
        """Report chaos event to test coordinator."""
        return await self._make_request(
            "report_chaos_event",
            self._stub.report_chaos_event,
            chaos_event
        )

    async def get_active_scenarios(self) -> List[ScenarioStatus]:
        """Get list of active test scenarios."""
        response = await self._make_request(
            "get_active_scenarios",
            self._stub.get_active_scenarios,
            {}
        )
        return response.get("scenarios", [])


class InterServiceClientManager:
    """
    Central manager for all inter-service gRPC clients.

    This manager provides:
    - Client lifecycle management with caching and pooling
    - Service discovery integration for dynamic endpoint resolution
    - Centralized configuration and monitoring
    - Resource cleanup and connection management
    """

    def __init__(
        self,
        settings: Settings,
        service_discovery: Optional[ServiceDiscovery] = None
    ):
        self.settings = settings
        self.service_discovery = service_discovery

        # Client management
        self._clients: Dict[str, BaseGrpcClient] = {}
        self._initialized = False

        self._logger = logger.bind(
            component="inter_service_client_manager",
            service="trading-engine",
            environment=settings.environment
        )

    async def initialize(self):
        """Initialize the client manager."""
        if self._initialized:
            return

        self._logger.info("Initializing inter-service client manager")
        self._initialized = True
        self._logger.info("Inter-service client manager initialized")

    async def get_risk_monitor_client(self, use_fallback: bool = False) -> RiskMonitorClient:
        """Get or create risk monitor gRPC client."""
        if "risk-monitor" in self._clients:
            return self._clients["risk-monitor"]

        # Resolve endpoint
        host, port = await self._resolve_endpoint(
            "risk-monitor",
            DEFAULT_RISK_MONITOR_PORT,
            use_fallback
        )

        # Create and cache client
        client = RiskMonitorClient(host, port, self.settings)
        self._clients["risk-monitor"] = client

        self._logger.info(
            "Created risk monitor client",
            host=host,
            port=port
        )

        return client

    async def get_test_coordinator_client(self, use_fallback: bool = False) -> CoordinatorGrpcClient:
        """Get or create test coordinator gRPC client."""
        if "test-coordinator" in self._clients:
            return self._clients["test-coordinator"]

        # Resolve endpoint
        host, port = await self._resolve_endpoint(
            "test-coordinator",
            DEFAULT_TEST_COORDINATOR_PORT,
            use_fallback
        )

        # Create and cache client
        client = CoordinatorGrpcClient(host, port, self.settings)
        self._clients["test-coordinator"] = client

        self._logger.info(
            "Created test coordinator client",
            host=host,
            port=port
        )

        return client

    async def _resolve_endpoint(
        self,
        service_name: str,
        default_port: int,
        use_fallback: bool = False
    ) -> tuple[str, int]:
        """Resolve service endpoint via service discovery or fallback."""
        if self.service_discovery and not use_fallback:
            try:
                service_info = await self.service_discovery.get_service(service_name)
                if service_info:
                    self._logger.debug(
                        "Resolved service endpoint via service discovery",
                        service=service_name,
                        host=service_info.host,
                        port=service_info.grpc_port
                    )
                    return service_info.host, service_info.grpc_port
            except Exception as e:
                self._logger.warning(
                    "Failed to resolve service via service discovery, using fallback",
                    service=service_name,
                    error=str(e)
                )

        # Fallback to localhost and default port
        host = "localhost"
        port = default_port
        self._logger.debug(
            "Using fallback service endpoint",
            service=service_name,
            host=host,
            port=port
        )
        return host, port

    def get_manager_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        return {
            "total_clients": len(self._clients),
            "active_connections": sum(1 for client in self._clients.values() if client.is_connected),
            "initialized": self._initialized,
            "service_discovery_enabled": self.service_discovery is not None,
            "client_types": list(self._clients.keys())
        }

    async def cleanup(self):
        """Clean up all clients and resources."""
        self._logger.info("Cleaning up inter-service client manager")

        # Cleanup all clients
        for service_name, client in self._clients.items():
            try:
                await client.cleanup()
            except Exception as e:
                self._logger.error(
                    "Error cleaning up client",
                    service=service_name,
                    error=str(e)
                )

        # Reset state
        self._clients.clear()
        self._initialized = False

        self._logger.info("Inter-service client manager cleanup completed")


# Mock stubs for testing (would be replaced with generated protobuf stubs in production)
class MockRiskMonitorStub:
    """Mock risk monitor gRPC stub for testing."""

    def __init__(self, channel):
        self.channel = channel

    async def health_check(self, request):
        """Mock health check."""
        return HealthResponse(status="SERVING", service="risk-monitor")

    async def submit_strategy_status(self, strategy_status):
        """Mock strategy status submission."""
        return {"success": True, "message": "Status received"}

    async def get_risk_metrics(self, request):
        """Mock risk metrics retrieval."""
        return {
            "position_limit_utilization": 0.75,
            "total_exposure": 750000.0,
            "risk_score": 0.65
        }


class MockTestCoordinatorStub:
    """Mock test coordinator gRPC stub for testing."""

    def __init__(self, channel):
        self.channel = channel

    async def health_check(self, request):
        """Mock health check."""
        return HealthResponse(status="SERVING", service="test-coordinator")

    async def submit_scenario_status(self, scenario_status):
        """Mock scenario status submission."""
        return {"success": True, "scenario_id": scenario_status.scenario_id}

    async def report_chaos_event(self, chaos_event):
        """Mock chaos event reporting."""
        return {"acknowledged": True, "event_id": chaos_event.event_id}

    async def get_active_scenarios(self, request):
        """Mock active scenarios retrieval."""
        return {
            "scenarios": [
                ScenarioStatus(
                    scenario_id="load_test_001",
                    status="RUNNING",
                    start_time=datetime.now(UTC).isoformat()
                )
            ]
        }