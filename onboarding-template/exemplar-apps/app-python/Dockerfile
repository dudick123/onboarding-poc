# Installs dependencies via uv from pyproject.toml, runs with uvicorn.
# For reproducible builds: run `uv lock` and commit uv.lock, then change
# `uv sync --no-dev` below to `uv sync --frozen --no-dev` and add
# `COPY uv.lock ./` before the sync step.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --no-dev
COPY . .
EXPOSE 8080
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
