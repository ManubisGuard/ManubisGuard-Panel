ARG PYTHON_VERSION=3.14

FROM oven/bun:1 AS bun

FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /build
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

ADD . /build

# Install the exact dashboard dependencies from bun.lock during the image build.
COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun
RUN cd /build/dashboard && bun install --frozen-lockfile

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Pre-build the dashboard so production containers do not perform a Vite build at startup.
RUN cd /build/dashboard && bun run build --outDir build --assetsDir statics && test -s build/index.html

FROM python:${PYTHON_VERSION}-slim-trixie

COPY --from=builder /build /code
WORKDIR /code

# Bun is required at application startup because the dashboard is built there.
COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun

ENV PATH="/code/.venv/bin:/usr/local/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    postgresql-client \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY cli_wrapper.sh /usr/bin/pasarguard-cli
RUN chmod +x /usr/bin/pasarguard-cli

COPY tui_wrapper.sh /usr/bin/pasarguard-tui
RUN chmod +x /usr/bin/pasarguard-tui

COPY healthcheck.sh /code/healthcheck.sh
RUN chmod +x /code/healthcheck.sh

RUN chmod +x /code/start.sh

ENTRYPOINT ["/code/start.sh"]
