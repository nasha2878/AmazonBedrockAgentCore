FROM python:3.11-slim

# --------------------------------------------------
# Environment
# --------------------------------------------------
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# OpenTelemetry - CRITICAL for AgentCore Evaluations
ENV AGENT_OBSERVABILITY_ENABLED=true
ENV OTEL_PYTHON_DISTRO=aws_distro
ENV OTEL_PYTHON_CONFIGURATOR=aws_configurator
ENV OTEL_RESOURCE_ATTRIBUTES=service.name=<<AGENT ID>>,aws.log.group.names=/aws/bedrock-agentcore/runtimes/<<AGENT ID>>
ENV OTEL_EXPORTER_OTLP_LOGS_HEADERS=x-aws-log-group=/aws/bedrock-agentcore/runtimes/<<AGENT ID>>,x-aws-log-stream=runtime-logs,x-aws-metric-namespace=bedrock-agentcore
ENV OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
ENV OTEL_TRACES_EXPORTER=otlp

# CRITICAL: Enable auto-instrumentation
ENV OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true

# --------------------------------------------------
# Working directory
# --------------------------------------------------
WORKDIR /app

# --------------------------------------------------
# System dependencies
# --------------------------------------------------
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    gcc \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# --------------------------------------------------
# Python dependencies
# --------------------------------------------------
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# --------------------------------------------------
# Copy application
# --------------------------------------------------
COPY app.py .

# --------------------------------------------------
# Security
# --------------------------------------------------
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app

USER app

# --------------------------------------------------
# AgentCore runtime port
# --------------------------------------------------
EXPOSE 8080

# --------------------------------------------------
# Healthcheck
# --------------------------------------------------
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8080/ping || exit 1

# --------------------------------------------------
# CRITICAL: Start with OpenTelemetry auto-instrumentation
# --------------------------------------------------
ENTRYPOINT ["opentelemetry-instrument", "python", "app.py"]