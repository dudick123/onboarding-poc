# Quick Start — React Build Repo

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Node.js | 20+ | https://nodejs.org/ or `nvm install 20` |
| npm | 10+ | Bundled with Node.js |
| Docker | 24+ | https://docs.docker.com/get-docker/ |
| Access to ADO project | — | Provided by platform team |

---

## Step 1 — Clone and run locally

```bash
git clone https://dev.azure.com/{ado-org}/{ado-project}/_git/{app-name}
cd {app-name}
npm install
npm run dev
```

Open http://localhost:5173 — you should see the React app (Vite default port).

---

## Step 2 — Run tests

```bash
# Single pass (same as CI):
npm test -- --run

# Watch mode:
npm test
```

Coverage reports land in `coverage/`.

---

## Step 3 — Production build

```bash
npm run build
# Output lands in build/ (configured in vite.config.ts)
```

---

## Step 4 — Build and run the Docker image locally

```bash
docker build -t {app-name}:local .
docker run --rm -p 80:80 {app-name}:local
```

Open http://localhost:80 — the nginx-served production build.

The Dockerfile copies from `build/` into `/usr/share/nginx/html`. If you change the Vite `outDir`, update the `COPY --from=build` line in the Dockerfile to match.

---

## Step 5 — Set the CONTAINER_IMAGE pipeline variable

1. In ADO, navigate to **Pipelines → {app-name} → Edit → Variables**
2. Add a variable named `CONTAINER_IMAGE` with value `myacr.azurecr.io/myorg/{app-name}`
3. Do not lock the variable (it is not a secret)

---

## Step 6 — Trigger the first pipeline run

Push a commit to `main` (or queue the pipeline manually in ADO).

Expected run sequence:

1. **Test stage** — vitest runs; JUnit + Cobertura results in the **Tests** tab
2. **Build stage** — Docker build (`npm ci && npm run build` inside builder stage) + push
3. **image-meta artifact** — published under **Artifacts**

---

## Step 7 — Verify the config-repo trigger

After the build pipeline completes on `main`, check **Pipelines → {app-name}-k8s-manifests** — a new run should queue within ~60 seconds.

---

## Common first issues

| Symptom | Fix |
|---------|-----|
| Port 5173 not opening | Vite's default dev port is 5173; confirm with `npm run dev` output |
| `npm test` runs in watch mode (blocks CI) | Use `npm test -- --run` for a single pass locally |
| Docker `COPY --from=build /app/build/` fails | Check `vite.config.ts` `build.outDir` — update the Dockerfile COPY if different |
| Pipeline coverage file not found | The pipeline looks for `coverage/cobertura-coverage.xml`; ensure vitest coverage reporter is set to `cobertura` in `vite.config.ts` |
