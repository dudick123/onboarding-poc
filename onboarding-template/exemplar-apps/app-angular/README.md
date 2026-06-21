# {app-name} — Angular Build Repo

Angular 18 SPA using standalone components and the esbuild application builder. This is the **build repo** in the three-repo GitOps model — it produces the container image that is promoted through environments by the `{app-name}-k8s-manifests` config repo.

## Run locally

```bash
npm install
npm start
# → http://localhost:4200
```

## Test locally

```bash
npx ng test --watch=false --browsers=ChromeHeadless
```

## Build

```bash
npm run build
# Output lands in dist/ (angular.json sets outputPath.browser: "")
```

## Docker

```bash
docker build -t {app-name} .
docker run -p 80:80 {app-name}
```

The Dockerfile uses a two-stage build: `node:20-alpine` compiles the Angular app; `nginx:alpine` serves the static assets. The runtime image has no Node.js toolchain.

The `dist/` directory structure produced by the Angular esbuild builder is served directly from nginx's document root.

## CI/CD pipeline

The `azure-pipelines.yml` pipeline runs on every push to `main`:

1. **Test** — `ng test` (headless Chrome + coverage), JUnit + Cobertura output published to ADO
2. **Build** — multi-stage Docker build, push to `$(CONTAINER_IMAGE)`, publish `image-meta` artifact

Set `CONTAINER_IMAGE` in **Pipeline → Edit → Variables** before the first run.

## Documentation

| Doc | What it covers |
|-----|----------------|
| [QUICK-START.md](QUICK-START.md) | First-time setup, prerequisites, local development |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Pipeline stages, image-meta artifact, config-repo trigger |
| [EXAMPLES.md](EXAMPLES.md) | Common pipeline and Dockerfile changes |
| [AGENT-SKILLS.md](AGENT-SKILLS.md) | Available Claude Code skills and how to use them |
