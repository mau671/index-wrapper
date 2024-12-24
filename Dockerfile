# Stage 1: Base environment with Python and essential tools
FROM python:3.12-slim AS base

# Install UV and other essential tools
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables
ENV LANG=C.UTF-8 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=America/Costa_Rica

# Install dependencies, Google Chrome, and unrar
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gnupg2 curl unzip wget && \
    echo "deb http://deb.debian.org/debian bookworm non-free" >> /etc/apt/sources.list && \
    echo "deb http://deb.debian.org/debian bookworm-updates non-free" >> /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends unrar && \
    curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Stage 2: Application build
FROM base AS build

# Set the working directory
WORKDIR /app

# Copy the project files
COPY . /app

# Install project dependencies
RUN uv sync --frozen --no-cache

# Stage 3: Final lightweight runtime
FROM base AS runtime

# Set the working directory
WORKDIR /app

# Copy the application from the build stage
COPY --from=build /app /app

ENTRYPOINT [ "uv", "run", "main.py" ]