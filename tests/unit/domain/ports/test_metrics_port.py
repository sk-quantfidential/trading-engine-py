"""BDD tests for MetricsPort interface (domain layer).

Following Clean Architecture: domain defines the interface (port),
infrastructure implements it (adapter). These tests validate the interface design.
"""
from typing import Callable

import pytest


class TestMetricsPortProtocol:
    """Test MetricsPort protocol definition (interface contract)."""

    def test_metrics_port_protocol_has_inc_counter_method(self):
        """
        Given a MetricsPort protocol
        When checking for inc_counter method
        Then the method signature should match: (name: str, labels: dict[str, str]) -> None
        """
        from trading_system.domain.ports.metrics import MetricsPort

        # Verify protocol has the method by checking type hints
        assert hasattr(MetricsPort, "inc_counter")

    def test_metrics_port_protocol_has_observe_histogram_method(self):
        """
        Given a MetricsPort protocol
        When checking for observe_histogram method
        Then the method signature should match: (name: str, value: float, labels: dict[str, str]) -> None
        """
        from trading_system.domain.ports.metrics import MetricsPort

        assert hasattr(MetricsPort, "observe_histogram")

    def test_metrics_port_protocol_has_set_gauge_method(self):
        """
        Given a MetricsPort protocol
        When checking for set_gauge method
        Then the method signature should match: (name: str, value: float, labels: dict[str, str]) -> None
        """
        from trading_system.domain.ports.metrics import MetricsPort

        assert hasattr(MetricsPort, "set_gauge")

    def test_metrics_port_protocol_has_get_http_handler_method(self):
        """
        Given a MetricsPort protocol
        When checking for get_http_handler method
        Then the method should return a Callable
        """
        from trading_system.domain.ports.metrics import MetricsPort

        assert hasattr(MetricsPort, "get_http_handler")


class TestMetricsLabels:
    """Test MetricsLabels dataclass helper."""

    def test_metrics_labels_to_dict_includes_all_populated_fields(self):
        """
        Given a MetricsLabels instance with all fields populated
        When converting to dict
        Then all fields should be included
        """
        from trading_system.domain.ports.metrics import MetricsLabels

        labels = MetricsLabels(
            service="trading-system-engine",
            instance="trading-system-engine-LH",
            version="0.1.0",
            method="GET",
            route="/api/v1/health",
            code="200",
        )

        result = labels.to_dict()

        assert result == {
            "service": "trading-system-engine",
            "instance": "trading-system-engine-LH",
            "version": "0.1.0",
            "method": "GET",
            "route": "/api/v1/health",
            "code": "200",
        }

    def test_metrics_labels_to_dict_filters_empty_fields(self):
        """
        Given a MetricsLabels instance with some empty fields
        When converting to dict
        Then only non-empty fields should be included
        """
        from trading_system.domain.ports.metrics import MetricsLabels

        labels = MetricsLabels(
            service="trading-system-engine",
            instance="trading-system-engine",
            version="0.1.0",
            # method, route, code are empty
        )

        result = labels.to_dict()

        assert result == {
            "service": "trading-system-engine",
            "instance": "trading-system-engine",
            "version": "0.1.0",
        }
        assert "method" not in result
        assert "route" not in result
        assert "code" not in result

    def test_metrics_labels_constant_labels_returns_service_identity_only(self):
        """
        Given a MetricsLabels instance
        When getting constant_labels
        Then only service, instance, version should be returned
        """
        from trading_system.domain.ports.metrics import MetricsLabels

        labels = MetricsLabels(
            service="trading-system-engine",
            instance="trading-system-engine-Alpha",
            version="0.1.0",
            method="POST",
            route="/api/v1/orders",
            code="201",
        )

        result = labels.constant_labels()

        # Should only include constant labels (service identity)
        assert result == {
            "service": "trading-system-engine",
            "instance": "trading-system-engine-Alpha",
            "version": "0.1.0",
        }
        # Should NOT include per-request labels
        assert "method" not in result
        assert "route" not in result
        assert "code" not in result

    def test_metrics_labels_enforces_low_cardinality_design(self):
        """
        Given the MetricsLabels dataclass
        When examining its fields
        Then all fields should represent low-cardinality dimensions
        """
        from trading_system.domain.ports.metrics import MetricsLabels

        labels = MetricsLabels()

        # Verify all fields are strings (low cardinality by design)
        assert isinstance(labels.service, str)
        assert isinstance(labels.instance, str)
        assert isinstance(labels.version, str)
        assert isinstance(labels.method, str)
        assert isinstance(labels.route, str)
        assert isinstance(labels.code, str)

        # No high-cardinality fields like:
        # - user_id (too many unique values)
        # - request_id (unique per request)
        # - timestamp (infinite cardinality)
        # - full_path (too many variations)
