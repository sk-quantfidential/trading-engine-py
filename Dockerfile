FROM python:3.13-slim

WORKDIR /app

# Install system dependencies including Docker CLI
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
#    curl \
#    && curl -fsSL https://get.docker.com -o get-docker.sh \
#    && sh get-docker.sh \
#    && rm get-docker.sh \

# Copy trading-data-adapter-py dependency first
COPY trading-data-adapter-py/ /app/trading-data-adapter-py/

# Copy requirements and install trading-system-engine
COPY trading-system-engine-py/pyproject.toml ./

# Install trading-data-adapter first
RUN pip install --no-cache-dir /app/trading-data-adapter-py

# Install trading-system-engine (without trading-data-adapter since already installed)
# RUN pip install --no-cache-dir -e .
RUN pip install --no-cache-dir \
    fastapi>=0.116.2 \
    uvicorn[standard]>=0.36.0 \
    pydantic>=2.11.9 \
    pydantic-settings>=2.10.1 \
    grpcio>=1.74.1 \
    grpcio-tools>=1.74.1 \
    grpcio-status>=1.68.0 \
    grpcio-health-checking>=1.74.0 \
    grpcio-reflection>=1.68.0 \
    anyio>=4.6.0 \
    asyncio-mqtt>=0.16.0 \
    structlog>=24.4.0 \
    prometheus-client>=0.23.1 \
    opentelemetry-api>=1.37.0 \
    opentelemetry-sdk>=1.37.0 \
    opentelemetry-instrumentation-fastapi>=0.58b0 \
    opentelemetry-instrumentation-grpc>=0.58b0 \
    opentelemetry-instrumentation-asyncio>=0.58b0 \
    opentelemetry-instrumentation-redis>=0.58b0 \
    opentelemetry-exporter-otlp-proto-grpc>=1.37.0 \
    httpx>=0.28.1 \
    tenacity>=9.1.2 \
    orjson>=3.11.3 \
    msgpack>=1.1.0

# Copy source code (directly to /app so trading_system is importable)
COPY trading-system-engine-py/src/ ./

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/v1/health')"
#    CMD curl -f http://localhost:8080/api/v1/health || exit 1

EXPOSE 8080 50051

CMD ["python", "-m", "trading_system.main"]