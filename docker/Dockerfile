# Build from the repository root:
#   docker compose -f docker/compose.yaml build

FROM python:3.14-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install locked dependencies first so code changes reuse this layer.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-install-project

COPY configs ./configs
COPY src ./src

ENV PATH="/app/.venv/bin:$PATH"

# .env and data/ are mounted at runtime, never baked into the image.
CMD ["python", "-m", "src.main"]
