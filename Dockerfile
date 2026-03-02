## Multi-stage build: builder creates wheels, runtime installs them system-wide
FROM python:3.12.4-slim AS builder
LABEL maintainer="Shuyib"
ENV DEBIAN_FRONTEND=noninteractive

# Install build-time dependencies for compiling wheels
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       gcc \
       libpq-dev \
       unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/

# Upgrade pip and build wheels into /wheels to be consumed by the runtime image
RUN python -m pip install --upgrade pip \
    && pip wheel --wheel-dir=/wheels -r requirements.txt


FROM python:3.12.4-slim
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Runtime dependencies; keep minimal and use --no-install-recommends
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl \
       graphviz \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy built wheels and application sources
COPY --from=builder /wheels /wheels
COPY . /app

# Install Python packages system-wide from wheels; fallback to requirements if needed
RUN pip install --no-cache-dir --no-deps /wheels/* || pip install --no-cache-dir -r /app/requirements.txt

# Create a dedicated non-root user and ensure proper ownership of application files
RUN groupadd -r adkuser \
    && useradd -r -g adkuser adkuser \
    && chown -R adkuser:adkuser /app

# Expose application port
EXPOSE 80

# Healthcheck for container orchestration
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:80/health || exit 1
# Runtime security recommendations (to apply when running the container):
#  - Mount secrets at runtime (do NOT COPY credentials into the image)
#    e.g. docker run -v /host/creds.json:/run/secrets/creds.json:ro -e GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/creds.json ...
#  - Run with: --read-only --tmpfs /tmp:rw,size=64m and drop capabilities in orchestration

# Switch to non-root user
USER adkuser

# Default command: run the ADK API server.
# AGENTS_DIR must be the *parent* directory whose subdirectories are agent packages.
# /app contains agentops_agent/ (and optionally my_agent/), so pass /app (i.e. ".").
CMD ["adk", "api_server", "--host", "0.0.0.0", "--port", "80", "."]
