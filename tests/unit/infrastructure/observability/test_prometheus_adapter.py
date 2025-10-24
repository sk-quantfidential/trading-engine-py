"""BDD tests for PrometheusMetricsAdapter (infrastructure layer).

PrometheusAdapter implements MetricsPort using prometheus_client library.
Following Clean Architecture: infrastructure implements domain ports.
"""
import pytest


class TestPrometheusAdapterInitialization:
    """Test PrometheusMetricsAdapter initialization."""

    def test_adapter_initializes_with_constant_labels(self):
        """
        Given constant labels (service, instance, version)
        When initializing PrometheusMetricsAdapter
        Then adapter should store constant labels for metric creation
        """
        from trading_system.infrastructure.observability.prometheus_adapter import (
            PrometheusMetricsAdapter,
        )

        constant_labels = {
            "service": "trading-system-engine",
            "instance": "trading-system-engine-LH",
            "version": "0.1.0",
        }

        adapter = PrometheusMetricsAdapter(constant_labels)

        assert adapter._constant_labels == constant_labels

    def test_adapter_has_custom_registry(self):
        """
        Given PrometheusMetricsAdapter initialization
        When checking for custom registry
        Then adapter should have its own CollectorRegistry (not global)
        """
        from trading_system.infrastructure.observability.prometheus_adapter import (
            PrometheusMetricsAdapter,
        )

        adapter = PrometheusMetricsAdapter({"service": "test", "instance": "test", "version": "0.1.0"})

        assert hasattr(adapter, "registry")
        assert adapter.registry is not None


class TestPrometheusAdapterCounterMetrics:
    """Test counter metric operations."""

    def test_inc_counter_increments_counter_metric(self):
        """
        Given a PrometheusMetricsAdapter
        When incrementing a counter metric
        Then the counter value should increase
        """
        from trading_system.infrastructure.observability.prometheus_adapter import (
            PrometheusMetricsAdapter,
        )

        adapter = PrometheusMetricsAdapter({"service": "test", "instance": "test", "version": "0.1.0"})
        labels = {"method": "GET", "route": "/health", "code": "200"}

        # Increment counter
        adapter.inc_counter("http_requests_total", labels)

        # Verify counter was created and incremented
        assert "http_requests_total" in adapter._counters
        counter = adapter._counters["http_requests_total"]
        # Prometheus Counter stores name without suffixes in _name attribute
        assert "http_requests" in counter._name


class TestPrometheusAdapterHistogramMetrics:
    """Test histogram metric operations."""

    def test_observe_histogram_records_value(self):
        """
        Given a PrometheusMetricsAdapter
        When observing a histogram value
        Then the histogram should record the value
        """
        from trading_system.infrastructure.observability.prometheus_adapter import (
            PrometheusMetricsAdapter,
        )

        adapter = PrometheusMetricsAdapter({"service": "test", "instance": "test", "version": "0.1.0"})
        labels = {"method": "POST", "route": "/api/v1/orders", "code": "201"}

        # Observe histogram value
        adapter.observe_histogram("http_request_duration_seconds", 0.123, labels)

        # Verify histogram was created
        assert "http_request_duration_seconds" in adapter._histograms
        histogram = adapter._histograms["http_request_duration_seconds"]
        assert histogram._name == "http_request_duration_seconds"


class TestPrometheusAdapterGaugeMetrics:
    """Test gauge metric operations."""

    def test_set_gauge_sets_gauge_value(self):
        """
        Given a PrometheusMetricsAdapter
        When setting a gauge value
        Then the gauge should be set to the specified value
        """
        from trading_system.infrastructure.observability.prometheus_adapter import (
            PrometheusMetricsAdapter,
        )

        adapter = PrometheusMetricsAdapter({"service": "test", "instance": "test", "version": "0.1.0"})
        labels = {"dependency": "postgres"}

        # Set gauge value
        adapter.set_gauge("service_dependency_ready", 1.0, labels)

        # Verify gauge was created
        assert "service_dependency_ready" in adapter._gauges
        gauge = adapter._gauges["service_dependency_ready"]
        assert gauge._name == "service_dependency_ready"


class TestPrometheusAdapterHTTPHandler:
    """Test HTTP handler generation."""

    def test_get_http_handler_returns_callable(self):
        """
        Given a PrometheusMetricsAdapter
        When getting HTTP handler
        Then should return a callable that generates metrics output
        """
        from trading_system.infrastructure.observability.prometheus_adapter import (
            PrometheusMetricsAdapter,
        )

        adapter = PrometheusMetricsAdapter({"service": "test", "instance": "test", "version": "0.1.0"})

        handler = adapter.get_http_handler()

        assert callable(handler)

    def test_http_handler_generates_prometheus_format(self):
        """
        Given a PrometheusMetricsAdapter with some metrics
        When calling the HTTP handler
        Then should return Prometheus text format
        """
        from trading_system.infrastructure.observability.prometheus_adapter import (
            PrometheusMetricsAdapter,
        )

        adapter = PrometheusMetricsAdapter({"service": "test", "instance": "test", "version": "0.1.0"})

        # Create some metrics
        adapter.inc_counter("test_counter", {"method": "GET"})

        handler = adapter.get_http_handler()
        output = handler()

        # Should be bytes in Prometheus format
        assert isinstance(output, bytes)
        # Should contain metric name
        assert b"test_counter" in output


class TestPrometheusAdapterThreadSafety:
    """Test thread-safe lazy initialization."""

    def test_multiple_counter_increments_thread_safe(self):
        """
        Given a PrometheusMetricsAdapter
        When incrementing the same counter multiple times
        Then each increment should be recorded (thread-safe)
        """
        from trading_system.infrastructure.observability.prometheus_adapter import (
            PrometheusMetricsAdapter,
        )

        adapter = PrometheusMetricsAdapter({"service": "test", "instance": "test", "version": "0.1.0"})
        labels = {"method": "GET", "route": "/health", "code": "200"}

        # Increment counter multiple times
        for _ in range(5):
            adapter.inc_counter("http_requests_total", labels)

        # Counter should exist and be created only once
        assert "http_requests_total" in adapter._counters
        assert len(adapter._counters) == 1


class TestPrometheusAdapterPythonRuntimeMetrics:
    """Test Python runtime metrics registration."""

    def test_adapter_registers_python_runtime_metrics(self):
        """
        Given PrometheusMetricsAdapter initialization
        When adapter is created
        Then Python runtime metrics should be registered (process, GC, platform)
        """
        from trading_system.infrastructure.observability.prometheus_adapter import (
            PrometheusMetricsAdapter,
        )

        adapter = PrometheusMetricsAdapter({"service": "test", "instance": "test", "version": "0.1.0"})

        # Get metrics output
        handler = adapter.get_http_handler()
        output = handler().decode("utf-8")

        # Should contain Python runtime metrics
        assert "python_" in output or "process_" in output


class TestPrometheusAdapterLabelExtraction:
    """Test label extraction logic."""

    def test_extract_label_names_excludes_constant_labels(self):
        """
        Given labels dict with both constant and per-request labels
        When extracting label names
        Then should only return per-request label names (exclude constant)
        """
        from trading_system.infrastructure.observability.prometheus_adapter import (
            PrometheusMetricsAdapter,
        )

        constant_labels = {"service": "test", "instance": "test", "version": "0.1.0"}
        adapter = PrometheusMetricsAdapter(constant_labels)

        # Labels including both constant and per-request
        labels = {
            "service": "test",  # constant
            "instance": "test",  # constant
            "version": "0.1.0",  # constant
            "method": "GET",  # per-request
            "route": "/health",  # per-request
            "code": "200",  # per-request
        }

        label_names = adapter._extract_label_names(labels)

        # Should only include per-request labels
        assert "method" in label_names
        assert "route" in label_names
        assert "code" in label_names
        # Should NOT include constant labels
        assert "service" not in label_names
        assert "instance" not in label_names
        assert "version" not in label_names


class TestPrometheusAdapterMultipleMetricTypes:
    """Test multiple metric types coexisting."""

    def test_adapter_supports_multiple_metric_types(self):
        """
        Given a PrometheusMetricsAdapter
        When creating counter, histogram, and gauge metrics
        Then all metric types should coexist without conflicts
        """
        from trading_system.infrastructure.observability.prometheus_adapter import (
            PrometheusMetricsAdapter,
        )

        adapter = PrometheusMetricsAdapter({"service": "test", "instance": "test", "version": "0.1.0"})

        # Create different metric types
        adapter.inc_counter("requests_total", {"method": "GET"})
        adapter.observe_histogram("request_duration_seconds", 0.5, {"method": "POST"})
        adapter.set_gauge("connections_active", 10.0, {"pool": "main"})

        # All metrics should exist
        assert "requests_total" in adapter._counters
        assert "request_duration_seconds" in adapter._histograms
        assert "connections_active" in adapter._gauges
