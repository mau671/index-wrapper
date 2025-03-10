FROM python:3.12-alpine3.20

# Install UV 
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install unrar
COPY --from=ghcr.io/linuxserver/unrar:7.0.9 /usr/bin/unrar-alpine /bin/unrar

# Install dependencies
RUN apk add --no-cache unzip chromium chromium-chromedriver

# Set the working directory
WORKDIR /app

# Copy the project files
COPY . /app

# Install project dependencies
RUN uv sync --no-cache

# Set the entrypoint
ENTRYPOINT [ "uv", "run", "main.py" ]