# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

# Copy workspace definition files first so dependency layers can be cached
COPY pyproject.toml uv.lock ./
COPY common/ common/
COPY skills/ skills/
COPY mcp_server/ mcp_server/

# Install all workspace dependencies (frozen = use exact uv.lock versions)
RUN uv sync --all-packages --frozen

# Pre-download the sentence-transformers model used by analyze_financial_news.
# This bakes the model into the image so there is no slow cold-start on first use.
RUN uv run python -c \
    "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

EXPOSE 35001

ENV REPO_ROOT=/app

CMD ["uv", "run", "python", "-m", "mcp_server.server"]
