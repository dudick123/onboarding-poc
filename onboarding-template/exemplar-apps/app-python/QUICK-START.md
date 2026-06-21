# Quick Start — Python Build Repo

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.12+ | https://python.org/downloads/ |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Docker | 24+ | https://docs.docker.com/get-docker/ |
| Access to ADO project | — | Provided by platform team |

---

## Step 1 — Clone and run locally

```bash
git clone https://dev.azure.com/{ado-org}/{ado-project}/_git/{app-name}
cd {app-name}
uv sync
uv run uvicorn main:app --reload --port 8080
```

Open http://localhost:8080 — you should see `{"message":"Hello, World!"}`.
Open http://localhost:8080/health — you should see `{"status":"ok"}`.
Open http://localhost:8080/docs — FastAPI Swagger UI.

---

## Step 2 — Run tests

```bash
uv run pytest
```

With coverage:

```bash
uv run pytest --cov=. --cov-report=term-missing
```

---

## Step 3 — Generate the lock file (first time)

The Dockerfile uses `uv sync --frozen --no-dev`, which requires `uv.lock` to be committed. If it does not exist yet:

```bash
uv lock
git add uv.lock
git commit -m "chore: add uv.lock"
```

This is a one-time step. After that, `uv lock` only needs to be re-run when you change `pyproject.toml`.

---

## Step 4 — Build and run the Docker image locally

```bash
docker build -t {app-name}:local .
docker run --rm -p 8080:8080 {app-name}:local
```

Test the containerized app:

```bash
curl http://localhost:8080/health
# {"status":"ok"}
```

---

## Step 5 — Set the CONTAINER_IMAGE pipeline variable

1. In ADO, navigate to **Pipelines → {app-name} → Edit → Variables**
2. Add a variable named `CONTAINER_IMAGE` with value `myacr.azurecr.io/myorg/{app-name}`
3. Do not lock the variable (it is not a secret)

---

## Step 6 — Trigger the first pipeline run

Push a commit to `main` (or queue the pipeline manually in ADO).

Expected run sequence:

1. **Test stage** — `uv run pytest` runs; results appear in the **Tests** tab
2. **Build stage** — Docker build + push; image lands in the registry
3. **image-meta artifact** — published; visible under **Artifacts** in the run summary

---

## Step 7 — Verify the config-repo trigger

After the build pipeline completes on `main`, check **Pipelines → {app-name}-k8s-manifests** — a new run should queue within ~60 seconds.

---

## Common first issues

| Symptom | Fix |
|---------|-----|
| `uv sync` fails with Python version error | Install Python 3.12+ and ensure it is on `PATH`, or use `uv python install 3.12` |
| Docker build fails with `uv.lock not found` | Run `uv lock` and commit the file before building |
| Import errors when running uvicorn | Run `uv sync` to ensure virtual env is up to date |
| Pipeline fails at Docker push | Service connection for container registry not configured; raise with platform team |
