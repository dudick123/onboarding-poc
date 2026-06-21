# {app-name} — React Build Repo

React 18 SPA using Vite and TypeScript. This is the **build repo** in the three-repo GitOps model — it produces the container image that is promoted through environments by the `{app-name}-k8s-manifests` config repo.

## Run locally

```bash
npm install
npm run dev
# → http://localhost:5173
```

## Test locally

```bash
npm test
# Runs vitest in watch mode; use `npm test -- --run` for a single pass
```

## Build

```bash
npm run build
# Output lands in build/ (configured in vite.config.ts)
```

## Docker

```bash
docker build -t {app-name} .
docker run -p 80:80 {app-name}
```

The Dockerfile uses a two-stage build: `node:20-alpine` compiles the Vite bundle; `nginx:alpine` serves the static assets. The runtime image has no Node.js toolchain.

## CI/CD pipeline

The `azure-pipelines.yml` pipeline runs on every push to `main`:

1. **Test** — `vitest` with JUnit + Cobertura output published to ADO
2. **Build** — multi-stage Docker build, push to `$(CONTAINER_IMAGE)`, publish `image-meta` artifact

Set `CONTAINER_IMAGE` in **Pipeline → Edit → Variables** before the first run.

## Documentation

| Doc | What it covers |
|-----|----------------|
| [QUICK-START.md](QUICK-START.md) | First-time setup, prerequisites, local development |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Pipeline stages, image-meta artifact, config-repo trigger |
| [EXAMPLES.md](EXAMPLES.md) | Common pipeline and Dockerfile changes |
| [AGENT-SKILLS.md](AGENT-SKILLS.md) | Available Claude Code skills and how to use them |
