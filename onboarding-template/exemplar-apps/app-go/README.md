# {app-name} — Go Build Repo

Minimal Go 1.22 HTTP service. This is the **build repo** in the three-repo GitOps model — it produces the container image that is promoted through environments by the `{app-name}-k8s-manifests` config repo.

## Endpoints

- `GET /` — returns `{"message": "Hello, World!"}`
- `GET /health` — returns `{"status": "ok"}`

## Run locally

```bash
go run .
# → http://localhost:8080
```

## Test locally

```bash
go test ./...

# With coverage:
go test -coverprofile=coverage.out ./...
go tool cover -func=coverage.out
```

## Docker

```bash
docker build -t {app-name} .
docker run -p 8080:8080 {app-name}
```

The Dockerfile uses a two-stage build: `golang:1.22-alpine` compiles the binary; `alpine:3.19` serves it. The runtime image has no Go toolchain.

## CI/CD pipeline

The `azure-pipelines.yml` pipeline runs on every push to `main`:

1. **Test** — `gotestsum` with JUnit + Cobertura output, published to ADO
2. **Build** — multi-stage Docker build, push to `$(CONTAINER_IMAGE)`, publish `image-meta` artifact

Set `CONTAINER_IMAGE` in **Pipeline → Edit → Variables** before the first run.

## Documentation

| Doc | What it covers |
|-----|----------------|
| [QUICK-START.md](QUICK-START.md) | First-time setup, prerequisites, local development |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Pipeline stages, image-meta artifact, config-repo trigger |
| [EXAMPLES.md](EXAMPLES.md) | Common pipeline and Dockerfile changes |
| [AGENT-SKILLS.md](AGENT-SKILLS.md) | Available Claude Code skills and how to use them |
