# {app-name} — Python Build Repo

FastAPI application running on uvicorn with [uv](https://docs.astral.sh/uv/) for dependency management. This is the **build repo** in the three-repo GitOps model — it produces the container image that is promoted through environments by the `{app-name}-k8s-manifests` config repo.

## Endpoints

- `GET /` — returns `{"message": "Hello, World!"}`
- `GET /health` — returns `{"status": "ok"}`
- `GET /docs` — Swagger UI (FastAPI built-in)

## Run locally

```bash
uv sync
uv run uvicorn main:app --reload --port 8080
# → http://localhost:8080
```

## Test locally

```bash
uv run pytest
uv run pytest --cov=. --cov-report=term-missing   # with coverage
```

## Lock file

Commit `uv.lock` alongside `pyproject.toml`. Regenerate it with:

```bash
uv lock
```

## Docker

```bash
uv lock    # must be committed before docker build
docker build -t {app-name} .
docker run -p 8080:8080 {app-name}
```

The Dockerfile copies `uv` from its official image and installs dependencies via `uv sync --frozen --no-dev`. The `uv.lock` file must be committed for reproducible container builds.

## CI/CD pipeline

The `azure-pipelines.yml` pipeline runs on every push to `main`:

1. **Test** — `uv run pytest` with JUnit + Cobertura output, published to ADO
2. **Build** — multi-stage Docker build, push to `$(CONTAINER_IMAGE)`, publish `image-meta` artifact

Set `CONTAINER_IMAGE` in **Pipeline → Edit → Variables** before the first run.

## Documentation

| Doc | What it covers |
|-----|----------------|
| [QUICK-START.md](QUICK-START.md) | First-time setup, prerequisites, local development |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Pipeline stages, image-meta artifact, config-repo trigger |
| [EXAMPLES.md](EXAMPLES.md) | Common pipeline and Dockerfile changes |
| [AGENT-SKILLS.md](AGENT-SKILLS.md) | Available Claude Code skills and how to use them |
