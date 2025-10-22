# Pull Request: TSE-0001.12.0b - Prometheus Metrics with Clean Architecture (trading-system-engine-py)

**Epic:** TSE-0001 - Foundation Services & Infrastructure
**Milestone:** TSE-0001.12.0b - Prometheus Metrics (Clean Architecture)
**Branch:** `feature/TSE-0001.12.0b-prometheus-metrics-client`
**Status:** ✅ Ready for Review
**Date:** 2025-10-09

## Summary

This PR implements Prometheus metrics collection for trading-system-engine-py using **Clean Architecture principles** (port/adapter pattern), following the proven implementation from risk-monitor-py and audit-correlator-go. The domain layer never depends on infrastructure concerns, enabling future migration to OpenTelemetry without changing domain, application, or presentation logic.

**Key Achievements:**
1. ✅ **Clean Architecture**: MetricsPort interface in domain layer
2. ✅ **RED Pattern**: Rate, Errors, Duration metrics for all HTTP requests
3. ✅ **Low Cardinality**: Proper label design prevents metric explosion
4. ✅ **Future-Proof**: Can swap Prometheus for OpenTelemetry by changing adapter only
5. ✅ **Testable**: Mock MetricsPort for unit tests without prometheus_client
6. ✅ **Comprehensive Tests**: 19 new tests passing (8 domain + 11 adapter)
7. ✅ **All 138 tests passing** (119 existing + 19 new)

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                   Presentation Layer                        │
│  ┌────────────────┐  ┌──────────────────────────────────┐  │
│  │ Metrics Router │  │  RED Metrics Middleware          │  │
│  │  /metrics      │  │  (FastAPI middleware)            │  │
│  └────────┬───────┘  └──────────────┬───────────────────┘  │
│           │                          │                      │
└───────────┼──────────────────────────┼──────────────────────┘
            │   depends on interface   │
            ▼                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  Domain Layer (Port)                        │
│  ┌───────────────────────────────────────────────────────┐ │
│  │          MetricsPort (Protocol)                       │ │
│  │  - inc_counter(name, labels)                          │ │
│  │  - observe_histogram(name, value, labels)             │ │
│  │  - set_gauge(name, value, labels)                     │ │
│  │  - get_http_handler() -> Callable                     │ │
│  └───────────────────────────────────────────────────────┘ │
└───────────────────────┬─────────────────────────────────────┘
                        │  implemented by adapter
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              Infrastructure Layer (Adapter)                 │
│  ┌───────────────────────────────────────────────────────┐ │
│  │      PrometheusMetricsAdapter                         │ │
│  │  implements MetricsPort                               │ │
│  │                                                        │ │
│  │  - Uses prometheus_client library                     │ │
│  │  - Thread-safe lazy initialization                    │ │
│  │  - Registers Python runtime metrics                   │ │
│  │  - Applies constant labels (service, instance, ver)   │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Changes

### 1. Domain Layer - MetricsPort Interface (NEW)

**File:** `src/trading_system/domain/ports/metrics.py`
**Purpose:** Define contract for metrics collection, independent of implementation

**Interface:**
- `inc_counter(name, labels)` - Increment counters (requests_total, errors_total)
- `observe_histogram(name, value, labels)` - Record durations (request_duration_seconds)
- `set_gauge(name, value, labels)` - Set point-in-time values (connections, queue depth)
- `get_http_handler()` - Return callable for /metrics endpoint

**Helper:**
- `MetricsLabels` dataclass with `to_dict()` and `constant_labels()` methods
- Enforces low cardinality by design

**Clean Architecture Benefits:**
- Domain never imports prometheus_client
- Interface can be mocked for testing
- Future implementations (OpenTelemetry) implement same protocol

### 2. Infrastructure - PrometheusMetricsAdapter (NEW)

**File:** `src/trading_system/infrastructure/observability/prometheus_adapter.py`
**Purpose:** Implement MetricsPort using Prometheus client library

**Features:**
- Thread-safe lazy initialization of metrics
- Custom registry (avoids global state)
- Python runtime metrics (process_*, python_gc_*)
- Sensible histogram buckets (5ms to 10s)
- Constant labels applied to all metrics

**Tests:** 11 comprehensive tests covering:
- Counter increment
- Histogram observation
- Gauge setting
- HTTP handler generation
- Thread safety
- Python runtime metrics
- Multiple metric types coexistence

### 3. Infrastructure - Clean Architecture Middleware (NEW)

**File:** `src/trading_system/infrastructure/observability/metrics_middleware.py`
**Purpose:** FastAPI middleware using MetricsPort (not prometheus_client)

**RED Pattern Metrics:**
- `http_requests_total` - Counter (Rate)
- `http_request_duration_seconds` - Histogram (Duration)
- `http_request_errors_total` - Counter for 4xx/5xx (Errors)

**Labels:** method, route, code (low cardinality)

### 4. Presentation - Metrics Router (NEW)

**File:** `src/trading_system/presentation/metrics.py`
**Changes:** Created /api/v1/metrics endpoint using MetricsPort

**Implementation:**
```python
metrics_port = request.app.state.metrics_port
handler = metrics_port.get_http_handler()
return Response(content=handler())
```

### 5. Application Integration (UPDATED)

**File:** `src/trading_system/main.py`
**Changes:** Initialize PrometheusMetricsAdapter, register middleware and router

**Integration:**
```python
# Initialize metrics adapter
constant_labels = {
    "service": settings.service_name,
    "instance": settings.service_instance_name,
    "version": settings.version,
}
metrics_port = PrometheusMetricsAdapter(constant_labels)

# Store in app state
app.state.metrics_port = metrics_port

# Register middleware
app.middleware("http")(create_red_metrics_middleware(metrics_port))

# Register router
app.include_router(metrics_router, prefix="/api/v1/metrics", tags=["metrics"])
```

### 6. Configuration Fix (UPDATED)

**File:** `src/trading_system/infrastructure/config.py`
**Changes:** Fixed default ports to match TSE-0001.12.0 standard (8083/50053)

## Testing

**New Tests:** 19 tests created
- Domain layer: 8 tests for MetricsPort and MetricsLabels
- Infrastructure: 11 tests for PrometheusMetricsAdapter

**All Tests:** 138 passed (119 existing + 19 new)

**Coverage:**
- domain/ports/metrics.py: 89%
- prometheus_adapter.py: 92%
- Overall project: 69% (includes legacy code)

## Migration Notes

**Breaking Changes:** None - internal additions only

**New Endpoint:** `/api/v1/metrics` - Prometheus text format

## BDD Acceptance Criteria

✅ Trading System Engine exposes /api/v1/metrics endpoint with Prometheus format
✅ RED pattern metrics collected for all HTTP requests
✅ Metrics use Clean Architecture (MetricsPort abstraction)
✅ Domain layer has zero Prometheus dependencies
✅ Can mock MetricsPort for testing
✅ Python runtime metrics included
✅ Constant labels applied (service, instance, version)
✅ Future OpenTelemetry migration requires only adapter swap

## Files Modified/Created

**New Files (7):**
1. `src/trading_system/domain/ports/__init__.py`
2. `src/trading_system/domain/ports/metrics.py` (140 lines)
3. `src/trading_system/infrastructure/observability/__init__.py`
4. `src/trading_system/infrastructure/observability/prometheus_adapter.py` (191 lines)
5. `src/trading_system/infrastructure/observability/metrics_middleware.py` (74 lines)
6. `src/trading_system/presentation/metrics.py` (27 lines)
7. `docs/implementation/TSE-0001.12.0b-prometheus-metrics.md`

**Modified Files (2):**
1. `src/trading_system/main.py` (+17 lines)
2. `src/trading_system/infrastructure/config.py` (fixed default ports)

**Test Files Created (2):**
1. `tests/unit/domain/ports/test_metrics_port.py` (8 tests, 175 lines)
2. `tests/unit/infrastructure/observability/test_prometheus_adapter.py` (11 tests, 282 lines)

**Total Changes:** 9 files created/modified, +906 lines

## Future Work

- Add OpenTelemetry adapter implementing same MetricsPort interface
- Add integration tests for metrics endpoint
- Add Grafana dashboards for RED metrics
- Consider adding business metrics (orders_total, positions_active, etc.)

---

**Pull Request Checklist:**
- [x] Feature branch created
- [x] Implementation plan documented
- [x] TDD red-green cycles followed
- [x] All new tests passing (19/19)
- [x] Clean Architecture compliance verified
- [x] No domain layer infrastructure dependencies
- [x] All existing tests still passing (138/138 total)
- [x] PR documentation created
- [ ] TODO files updated
- [ ] Commits created

**Created:** 2025-10-09
**Author:** Claude Code (TSE Trading Ecosystem Team)
**Epic:** TSE-0001 Foundation Services & Infrastructure
**Milestone:** TSE-0001.12.0b Prometheus Metrics (Clean Architecture)
