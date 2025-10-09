"""Main application entry point for Trading System Engine service."""
import asyncio
import logging
import signal
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
import uvicorn
from fastapi import FastAPI

from trading_data_adapter import AdapterConfig, create_adapter
from trading_system.infrastructure.config import get_settings
from trading_system.infrastructure.logging import setup_logging
from trading_system.infrastructure.observability.metrics_middleware import (
    create_red_metrics_middleware,
)
from trading_system.infrastructure.observability.prometheus_adapter import (
    PrometheusMetricsAdapter,
)
from trading_system.presentation.health import router as health_router
from trading_system.presentation.metrics import router as metrics_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    settings = get_settings()

    # Bind instance context to logger for all future logs
    logger = structlog.get_logger()
    logger = logger.bind(
        service_name=settings.service_name,
        instance_name=settings.service_instance_name,
        environment=settings.environment,
    )

    logger.info("Starting Trading System Engine service", version=settings.version)

    # Initialize trading data adapter with service identity
    adapter_config = AdapterConfig(
        service_name=settings.service_name,
        service_instance_name=settings.service_instance_name,
        environment=settings.environment,
        postgres_url=settings.postgres_url,
        redis_url=settings.redis_url,
    )
    adapter = await create_adapter(adapter_config)

    # Store adapter in app state for access in routes
    app.state.trading_adapter = adapter

    logger.info("Trading data adapter initialized",
                postgres_connected=adapter.connection_status.postgres_connected,
                redis_connected=adapter.connection_status.redis_connected)

    # Startup logic here
    yield

    # Shutdown logic here
    logger.info("Shutting down Trading System Engine service")

    # Disconnect adapter
    await adapter.disconnect()
    logger.info("Trading data adapter disconnected")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    # Initialize Prometheus metrics adapter (Clean Architecture)
    constant_labels = {
        "service": settings.service_name,
        "instance": settings.service_instance_name,
        "version": settings.version,
    }
    metrics_port = PrometheusMetricsAdapter(constant_labels)
    logger = structlog.get_logger()
    logger.info("Prometheus metrics adapter initialized")

    app = FastAPI(
        title="Trading System Engine API",
        description="Systematic trading with market making strategies",
        version=settings.version,
        lifespan=lifespan,
    )

    # Store metrics_port for access in routes and middleware
    app.state.metrics_port = metrics_port

    # RED metrics middleware (Clean Architecture: uses MetricsPort)
    app.middleware("http")(create_red_metrics_middleware(metrics_port))

    # Include routers
    app.include_router(health_router, prefix="/api/v1", tags=["health"])
    app.include_router(metrics_router, prefix="/api/v1/metrics", tags=["metrics"])

    return app


def setup_signal_handlers() -> None:
    """Setup graceful shutdown signal handlers."""
    def signal_handler(signum: int, frame) -> None:
        logging.info(f"Received signal {signum}, shutting down gracefully")
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


async def main() -> None:
    """Main application entry point."""
    setup_logging()
    setup_signal_handlers()

    settings = get_settings()
    app = create_app()

    config = uvicorn.Config(
        app=app,
        host=settings.host,
        port=settings.http_port,
        log_config=None,  # Use our own logging
        access_log=False,
    )

    server = uvicorn.Server(config)

    try:
        await server.serve()
    except KeyboardInterrupt:
        logging.info("Received shutdown signal")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())