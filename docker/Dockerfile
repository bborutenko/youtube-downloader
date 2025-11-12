FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl build-essential ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && ln -s /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /app

COPY . .

RUN uv venv /opt/venv && uv pip install --upgrade pip
RUN uv lock
RUN uv sync --frozen --no-dev


FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY . .

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uv", "run", "src/main.py"]
