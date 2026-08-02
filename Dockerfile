# One image serves both entrypoints:
#   - the MCP server  (default CMD, long-running service)
#   - the daily pipeline (compose overrides `command`, one-shot job)
#
# Both need the same workspace, so building them separately would duplicate the
# torch + embedding-model layers for no benefit.
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# tzdata so the container's idea of "today" matches the host's — the pipeline
# keys its run directories off the local date. Override TZ in .env if needed.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*
ENV TZ=Europe/London

# Run as an unprivileged fixed-UID user. Created before anything is copied so
# the venv is built owned by `app` — a later `chown -R /app` would duplicate
# the entire ~1GB dependency tree into a new layer.
RUN useradd --create-home --uid 10001 app
WORKDIR /app
RUN chown app:app /app
USER app

ENV REPO_ROOT=/app \
    PYTHONUNBUFFERED=1 \
    UV_CACHE_DIR=/home/app/.cache/uv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    HF_HOME=/app/.cache/huggingface

# The pipeline orchestrator shells out to `uv run <script>` ~10 times per run.
# Without these, every one of those re-resolves the lockfile and tries to sync.
ENV UV_FROZEN=1 \
    UV_NO_SYNC=1

COPY --chown=app:app pyproject.toml uv.lock ./
COPY --chown=app:app common/ common/
COPY --chown=app:app skills/ skills/
COPY --chown=app:app mcp_server/ mcp_server/

# --no-dev drops pytest/ruff; the lockfile pins torch to the CPU-only index
# (see pyproject.toml), which keeps ~6.5GB of CUDA wheels out of the image.
# Deliberately no BuildKit cache mount here — this must also build on the
# legacy builder, since Ubuntu's docker.io package ships without buildx.
RUN uv sync --all-packages --frozen --no-dev \
    && rm -rf /home/app/.cache/uv

# Bake the sentence-transformers model used by analyze_news into the image so
# there is no cold-start download on the first run.
RUN uv run python -c \
    "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Set only after the model is cached: the container never needs the HF Hub at
# runtime, so pin it offline rather than letting a hub outage fail a nightly run.
ENV HF_HUB_OFFLINE=1

# Skill output directories. These are named-volume mount points at runtime;
# creating them here as `app` means Docker seeds the volumes with the right
# ownership instead of root-owned mounts the container cannot write to.
RUN mkdir -p /app/skills/daily_pipeline/tmp \
             /app/skills/financial_news/tmp \
             /app/skills/trader/tmp \
             /app/skills/get_stock_portfolio/tmp \
             /app/skills/get_crypto_portfolio/tmp \
             /app/skills/check_stock/tmp \
             /app/skills/check_crypto/tmp

EXPOSE 35001

CMD ["uv", "run", "python", "-m", "mcp_server.server"]
