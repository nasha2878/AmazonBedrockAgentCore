# Dockerfile - Part 30: ADOT Observability Implementation
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# 1. Install Python dependencies (including aws-opentelemetry-distro)
RUN pip install --no-cache-dir -r requirements.txt

# 2. Install auto-instrumentation hooks (required for ADOT to see Boto3/Flask)
RUN opentelemetry-bootstrap -a install

# --- ADOT / AGENTCORE OBSERVABILITY CONFIG ---
# This activates the internal telemetry pipeline to the visual dashboard
ENV AGENT_OBSERVABILITY_ENABLED=true
ENV OTEL_PYTHON_DISTRO=aws_distro
ENV OTEL_PYTHON_CONFIGURATOR=aws_configurator
ENV OTEL_SERVICE_NAME=REI-Market-Intel-Agent

# Copy application code
COPY app.py .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Expose port 8080 (required for AgentCore)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/ping || exit 1

# 3. Use the opentelemetry-instrument wrapper to enable auto-tracing
ENTRYPOINT ["opentelemetry-instrument", "python", "app.py"]
