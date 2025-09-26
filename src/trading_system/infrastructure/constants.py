#!/usr/bin/env python3
"""
Infrastructure Constants

Centralized constants for trading system infrastructure components.
This module provides configuration values, timeouts, and other constants
used across the trading system infrastructure.
"""

# Configuration Service Constants
DEFAULT_CONFIG_SERVICE_PORT = 8090
DEFAULT_CACHE_TTL_SECONDS = 300  # 5 minutes
VALID_CONFIG_TYPES = ["string", "number", "boolean", "json"]

# gRPC Service Constants
DEFAULT_GRPC_TIMEOUT = 30.0  # 30 seconds
DEFAULT_RISK_MONITOR_PORT = 50054
DEFAULT_TEST_COORDINATOR_PORT = 50053

# Service Ports (for reference and consistency)
SERVICE_PORTS = {
    "trading-system-engine": {
        "http": 8082,
        "grpc": 50052
    },
    "risk-monitor": {
        "http": 8084,
        "grpc": 50054
    },
    "test-coordinator": {
        "http": 8083,
        "grpc": 50053
    },
    "configuration-service": {
        "http": 8090,
        "grpc": 50090
    }
}

# Circuit Breaker Constants
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 60  # seconds
CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS = 3

# Retry and Timeout Constants
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY_BASE = 1.0  # seconds
RETRY_DELAY_MAX = 10.0  # seconds
CONNECTION_TIMEOUT = 10.0  # seconds

# Performance and Monitoring Constants
STATS_COLLECTION_INTERVAL = 30  # seconds
METRICS_RETENTION_HOURS = 24
CACHE_CLEANUP_INTERVAL = 300  # 5 minutes

# OpenTelemetry Constants
OTEL_SERVICE_NAME = "trading-system-engine"
OTEL_SPAN_ATTRIBUTES = {
    "service.namespace": "trading-ecosystem",
    "service.instance.id": "trading-engine-001"
}

# Environment Constants
VALID_ENVIRONMENTS = ["development", "testing", "production"]
DEFAULT_ENVIRONMENT = "development"

# Resource Limits
MAX_CONCURRENT_CONNECTIONS = 100
MAX_CACHE_SIZE = 1000
MAX_MESSAGE_SIZE = 4 * 1024 * 1024  # 4MB

# Logging Constants
LOG_CORRELATION_ID_HEADER = "X-Correlation-ID"
LOG_REQUEST_ID_HEADER = "X-Request-ID"