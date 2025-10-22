FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy trading-data-adapter-py dependency first
COPY trading-data-adapter-py/ /app/trading-data-adapter-py/

# Install trading-data-adapter first
RUN pip install --no-cache-dir /app/trading-data-adapter-py

# Copy requirements and install trading-system-engine
COPY trading-system-engine-py/pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Copy source code (directly to /app so trading_system is importable)
COPY trading-system-engine-py/src/ ./

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8082/api/v1/health')"

EXPOSE 8082 50052

CMD ["python", "-m", "trading_system.main"]