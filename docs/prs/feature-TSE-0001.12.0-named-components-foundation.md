# PR: Named Components Foundation (TSE-0001.12.0) - trading-system-engine-py

**Branch**: `feature/TSE-0001.12.0-named-components-foundation`
**Epic**: TSE-0001 (Foundation Services & Infrastructure)
**Status**: ✅ READY FOR REVIEW
**Date**: 2025-10-08

## Summary

Implements multi-instance infrastructure foundation for trading-system-engine-py, enabling deployment as singleton (trading-system-engine) or multi-instance (trading-system-engine-LH, trading-system-engine-Alpha) with automatic PostgreSQL schema and Redis namespace derivation via trading-data-adapter-py.

## Changes Overview

### 1. Instance-Aware Configuration (config.py)
- Added `service_instance_name` with auto-derivation
- Added `environment: Literal["development", "testing", "production", "docker"]`
- Added `@field_validator` for log_level normalization
- Updated default ports: HTTP 8083, gRPC 50053

### 2. Health Endpoint Enhancement (health.py)
- Updated `HealthResponse`: service, instance, version, environment, timestamp
- Returns ISO 8601 UTC timestamps

### 3. Structured Logging (main.py)
- Logger binding with instance context in `lifespan()`
- All logs include: service_name, instance_name, environment

### 4. Data Adapter Integration (main.py)
- Pass service identity to adapter config
- Adapter derives schema/namespace automatically

### 5. Docker Build (Dockerfile)
- Fixed COPY paths for parent context
- Installs trading-data-adapter-py first
- Health check on port 8083

### 6. Docker Deployment (docker-compose.yml, prometheus.yml)
- Added trading-system-engine service (172.20.0.86:8083)
- Prometheus scraping with instance labels
- Environment variables for service identity

### 7. Comprehensive Testing (test_startup.py)
- 19 startup tests validating instance awareness
- All 119 tests passing (100 + 19)

## Test Results

**Total Tests**: 119/119 passing (100 existing + 19 startup)
**Coverage**: 69% (config layer 98%, main 57%, health 100%)

## BDD Acceptance

✅ Trading System Engine can be deployed as singleton or multi-instance with automatic schema/namespace derivation

**Files Modified**: 6 modified, 2 new (8 total)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
