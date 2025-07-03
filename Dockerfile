FROM python:3.12-slim as base

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Environment
ENV LANG=C.UTF-8 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=America/Costa_Rica

# System dependencies for Playwright + unrar
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        git \
        unzip \
        wget \
        gnupg \
        fontconfig \
        locales \
        libasound2 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libgbm1 \
        libgtk-3-0 \
        libnspr4 \
        libnss3 \
        libx11-xcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxrandr2 \
        libxkbcommon0 \
        libxshmfence1 \
        libxfixes3 \
        xdg-utils \
        unrar-free \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project
COPY . /app

# Install Python dependencies
RUN uv sync --no-cache

# Install Playwright browsers with system deps
RUN uv run python -m playwright install --with-deps --check

# Default entrypoint
ENTRYPOINT ["uv", "run", "main.py"]