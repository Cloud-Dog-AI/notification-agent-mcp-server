# Dockerfile for Notification Agent MCP Server
# Apache-2.0 (C) Cloud-Dog, Viewdeck Engineering Ltd.
# Multi-stage build for optimized image size

# --- [Proxy Configuration] ---
ARG HTTP_PROXY=""
ARG HTTPS_PROXY=""
ARG NO_PROXY=""
ARG http_proxy=""
ARG https_proxy=""
ARG no_proxy=""

FROM python:3.12-slim AS base
LABEL org.opencontainers.image.licenses="Apache-2.0"
LABEL org.opencontainers.image.vendor="Cloud-Dog, Viewdeck Engineering Limited"

ARG HTTP_PROXY=""
ARG HTTPS_PROXY=""
ARG NO_PROXY=""
ARG http_proxy=""
ARG https_proxy=""
ARG no_proxy=""

# Proxy environment variables (optional)
ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV NO_PROXY=${NO_PROXY}
ENV http_proxy=${http_proxy}
ENV https_proxy=${https_proxy}
ENV no_proxy=${no_proxy}

# Configure apt proxy (optional)
RUN if [ -n "$HTTP_PROXY" ]; then \
      echo "Acquire::http::Proxy \"$HTTP_PROXY\";" > /etc/apt/apt.conf.d/01proxy; \
      echo "Acquire::https::Proxy \"$HTTPS_PROXY\";" >> /etc/apt/apt.conf.d/01proxy; \
    fi

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    net-tools \
    procps \
    lsof \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libglib2.0-0 \
    libffi8 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libharfbuzz-subset0 \
    libfribidi0 \
    shared-mime-info \
    fonts-dejavu-core \
    fonts-noto-core \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install platform packages from public Gitea PyPI.
ARG PYPI_URL=https://gitea.cloud-dog.net/api/packages/Cloud-Dog-External/pypi/simple
RUN --mount=type=secret,id=pip_conf,target=/etc/pip.conf \
    pip install --no-cache-dir \
      --extra-index-url ${PYPI_URL} \
      --trusted-host gitea.cloud-dog.net \
      --trusted-host files.pythonhosted.org \
      cloud-dog-config \
      cloud-dog-logging \
      cloud-dog-api-kit==0.13.0 \
      "cloud-dog-idam>=0.5.2,<0.6" \
      cloud-dog-db \
      "cloud-dog-jobs==0.4.1" \
      cloud-dog-llm \
      cloud-dog-cache \
      cloud-dog-storage
COPY requirements.txt .
RUN --mount=type=secret,id=pip_conf,target=/etc/pip.conf \
    pip install --no-cache-dir \
      --trusted-host gitea.cloud-dog.net \
      --trusted-host files.pythonhosted.org \
      -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY ui/ ./ui/
COPY certs/ ./certs/
COPY database/ ./database/
COPY defaults.yaml .
COPY env.example ./env.example
COPY start_*.py ./
COPY server_control.sh ./server_control.sh
COPY docker-entrypoint.sh ./docker-entrypoint.sh
COPY docker-healthcheck.sh ./docker-healthcheck.sh

# Install custom CA bundle if provided
RUN if [ -f "/app/certs/ca.crt" ]; then \
      echo "Installing custom CA bundle from /app/certs/ca.crt"; \
      cp /app/certs/ca.crt /usr/local/share/ca-certificates/custom-ca.crt && \
      update-ca-certificates; \
    fi

# Create necessary directories
RUN mkdir -p logs cache database storage working private certs

# Non-root user for security
RUN useradd -m -u 1000 notifyuser && \
    chown -R notifyuser:notifyuser /app
USER notifyuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=5 \
    CMD /app/docker-healthcheck.sh

# Ensure scripts are executable
RUN chmod +x /app/server_control.sh /app/docker-entrypoint.sh /app/docker-healthcheck.sh

# Default command
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["all"]
