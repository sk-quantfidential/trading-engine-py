#!/usr/bin/env python3
"""
Behavior tests for Health Check Endpoints

This module contains comprehensive behavior-focused tests for the health check
endpoints following TDD principles. Tests validate expected behaviors rather than
implementation details.

🎯 Test Coverage:
- Health endpoint availability and response structure
- Readiness endpoint functionality and dependency validation
- FastAPI router integration behaviors
- Pydantic model validation and serialization
- Service health monitoring and status reporting
"""

import pytest
import pytest_asyncio
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from trading_system.presentation.health import (
    router,
    health_check,
    readiness_check,
    HealthResponse,
    ReadinessResponse
)
from trading_system.infrastructure.config import Settings


class TestHealthResponse:
    """Test HealthResponse data model behavior."""

    def test_health_response_creation(self):
        """Should create HealthResponse with required fields."""
        response = HealthResponse(
            status="healthy",
            service="trading-system-engine",
            version="1.0.0"
        )

        assert response.status == "healthy"
        assert response.service == "trading-system-engine"
        assert response.version == "1.0.0"

    def test_health_response_serialization(self):
        """Should serialize HealthResponse to JSON correctly."""
        response = HealthResponse(
            status="healthy",
            service="trading-system-engine",
            version="1.0.0"
        )

        json_data = response.model_dump()
        assert json_data["status"] == "healthy"
        assert json_data["service"] == "trading-system-engine"
        assert json_data["version"] == "1.0.0"


class TestReadinessResponse:
    """Test ReadinessResponse data model behavior."""

    def test_readiness_response_creation(self):
        """Should create ReadinessResponse with status and checks."""
        checks = {
            "exchange_api": "ok",
            "market_data_api": "ok",
            "redis": "ok"
        }
        response = ReadinessResponse(
            status="ready",
            checks=checks
        )

        assert response.status == "ready"
        assert len(response.checks) == 3
        assert response.checks["exchange_api"] == "ok"

    def test_readiness_response_with_empty_checks(self):
        """Should handle ReadinessResponse with empty checks."""
        response = ReadinessResponse(
            status="not_ready",
            checks={}
        )

        assert response.status == "not_ready"
        assert len(response.checks) == 0


class TestHealthCheckBehavior:
    """Test health check endpoint behaviors."""

    @pytest.fixture
    def app(self):
        """Create FastAPI app with health router for testing."""
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client for HTTP requests."""
        return TestClient(app)

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        return Settings(
            service_name="trading-system-engine",
            version="1.0.0",
            environment="testing"
        )

    def test_health_check_returns_healthy_status(self, client):
        """Should return healthy status with service information."""
        with patch('trading_system.presentation.health.get_settings') as mock_get_settings:
            mock_settings = Mock()
            mock_settings.version = "1.0.0"
            mock_get_settings.return_value = mock_settings

            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "trading-system-engine"
            assert data["version"] == "1.0.0"

    def test_readiness_check_returns_ready_status(self, client):
        """Should return ready status with dependency checks."""
        response = client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "checks" in data
        assert isinstance(data["checks"], dict)

    def test_readiness_check_includes_dependency_validation(self, client):
        """Should include validation for required dependencies."""
        response = client.get("/ready")
        data = response.json()

        # Should validate key dependencies
        checks = data["checks"]
        assert "exchange_api" in checks
        assert "market_data_api" in checks
        assert "redis" in checks

        # All checks should report status
        for check_name, status in checks.items():
            assert isinstance(status, str)
            assert len(status) > 0

    def test_health_endpoint_accepts_get_only(self, client):
        """Should only accept GET requests on health endpoint."""
        # GET should work
        get_response = client.get("/health")
        assert get_response.status_code == 200

        # POST should not be allowed
        post_response = client.post("/health")
        assert post_response.status_code == 405  # Method Not Allowed

    def test_readiness_endpoint_accepts_get_only(self, client):
        """Should only accept GET requests on readiness endpoint."""
        # GET should work
        get_response = client.get("/ready")
        assert get_response.status_code == 200

        # POST should not be allowed
        post_response = client.post("/ready")
        assert post_response.status_code == 405  # Method Not Allowed

    def test_health_check_logs_request(self, client):
        """Should log health check requests for monitoring."""
        with patch('trading_system.presentation.health.logger') as mock_logger:
            with patch('trading_system.presentation.health.get_settings') as mock_get_settings:
                mock_settings = Mock()
                mock_settings.version = "1.0.0"
                mock_get_settings.return_value = mock_settings

                client.get("/health")

                # Should log health check request
                mock_logger.info.assert_called_with("Health check requested")

    def test_readiness_check_logs_request(self, client):
        """Should log readiness check requests for monitoring."""
        with patch('trading_system.presentation.health.logger') as mock_logger:
            client.get("/ready")

            # Should log readiness check request
            mock_logger.info.assert_called_with("Readiness check requested")

    @pytest.mark.asyncio
    async def test_health_check_function_returns_health_response(self, mock_settings):
        """Should return properly structured HealthResponse object."""
        with patch('trading_system.presentation.health.get_settings', return_value=mock_settings):
            response = await health_check()

            assert isinstance(response, HealthResponse)
            assert response.status == "healthy"
            assert response.service == "trading-system-engine"
            assert response.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_readiness_check_function_returns_readiness_response(self):
        """Should return properly structured ReadinessResponse object."""
        response = await readiness_check()

        assert isinstance(response, ReadinessResponse)
        assert response.status == "ready"
        assert isinstance(response.checks, dict)
        assert len(response.checks) > 0

    def test_health_response_content_type_is_json(self, client):
        """Should return JSON content type for health endpoint."""
        with patch('trading_system.presentation.health.get_settings') as mock_get_settings:
            mock_settings = Mock()
            mock_settings.version = "1.0.0"
            mock_get_settings.return_value = mock_settings

            response = client.get("/health")

            assert "application/json" in response.headers.get("content-type", "")

    def test_readiness_response_content_type_is_json(self, client):
        """Should return JSON content type for readiness endpoint."""
        response = client.get("/ready")

        assert "application/json" in response.headers.get("content-type", "")

    def test_health_endpoint_response_structure_validation(self, client):
        """Should return response matching HealthResponse schema."""
        with patch('trading_system.presentation.health.get_settings') as mock_get_settings:
            mock_settings = Mock()
            mock_settings.version = "1.0.0"
            mock_get_settings.return_value = mock_settings

            response = client.get("/health")
            data = response.json()

            # Should have all required fields
            required_fields = {"status", "service", "version"}
            assert set(data.keys()) == required_fields

            # Fields should have correct types
            assert isinstance(data["status"], str)
            assert isinstance(data["service"], str)
            assert isinstance(data["version"], str)

    def test_readiness_endpoint_response_structure_validation(self, client):
        """Should return response matching ReadinessResponse schema."""
        response = client.get("/ready")
        data = response.json()

        # Should have all required fields
        required_fields = {"status", "checks"}
        assert set(data.keys()) == required_fields

        # Fields should have correct types
        assert isinstance(data["status"], str)
        assert isinstance(data["checks"], dict)

    def test_health_check_uses_settings_version(self, client):
        """Should use version from settings configuration."""
        test_version = "2.1.0"

        with patch('trading_system.presentation.health.get_settings') as mock_get_settings:
            mock_settings = Mock()
            mock_settings.version = test_version
            mock_get_settings.return_value = mock_settings

            response = client.get("/health")
            data = response.json()

            assert data["version"] == test_version

    def test_multiple_health_checks_behave_consistently(self, client):
        """Should return consistent responses across multiple requests."""
        with patch('trading_system.presentation.health.get_settings') as mock_get_settings:
            mock_settings = Mock()
            mock_settings.version = "1.0.0"
            mock_get_settings.return_value = mock_settings

            # Make multiple requests
            responses = []
            for _ in range(5):
                response = client.get("/health")
                responses.append(response.json())

            # All responses should be identical
            first_response = responses[0]
            for response in responses[1:]:
                assert response == first_response

    def test_health_router_integration_with_fastapi(self):
        """Should integrate properly with FastAPI router system."""
        # Verify router has the expected routes
        routes = [route.path for route in router.routes]
        assert "/health" in routes
        assert "/ready" in routes

        # Verify HTTP methods
        health_route = next(r for r in router.routes if r.path == "/health")
        ready_route = next(r for r in router.routes if r.path == "/ready")

        assert "GET" in health_route.methods
        assert "GET" in ready_route.methods

    @pytest.mark.asyncio
    async def test_health_check_handles_settings_error_gracefully(self):
        """Should handle settings retrieval errors gracefully."""
        with patch('trading_system.presentation.health.get_settings') as mock_get_settings:
            # Simulate settings error
            mock_get_settings.side_effect = Exception("Settings not available")

            # Should still attempt to create response
            with pytest.raises(Exception):
                await health_check()

    def test_readiness_check_dependency_status_format(self, client):
        """Should return dependency statuses in expected format."""
        response = client.get("/ready")
        data = response.json()

        checks = data["checks"]
        for service_name, status in checks.items():
            # Service names should be descriptive
            assert isinstance(service_name, str)
            assert len(service_name) > 0

            # Status should be meaningful
            assert isinstance(status, str)
            assert status in ["ok", "error", "unknown"]  # Expected status values