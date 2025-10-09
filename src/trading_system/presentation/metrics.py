"""Prometheus metrics endpoint (presentation layer)."""
from fastapi import APIRouter, Request, Response

router = APIRouter()


@router.get("")
async def metrics(request: Request) -> Response:
    """Prometheus metrics endpoint using MetricsPort abstraction.

    Returns metrics in Prometheus text format. Uses Clean Architecture:
    - Depends on MetricsPort interface (domain layer)
    - No direct dependency on prometheus_client (infrastructure layer)
    - Future OpenTelemetry migration requires only adapter swap
    """
    # Get metrics_port from app state (injected during app creation)
    metrics_port = request.app.state.metrics_port

    # Get the metrics handler from the port
    handler = metrics_port.get_http_handler()

    # Generate metrics output
    metrics_output = handler()

    return Response(
        content=metrics_output,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
