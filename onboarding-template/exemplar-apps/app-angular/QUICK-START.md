# Quick Start — Angular Build Repo

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Node.js | 20+ | https://nodejs.org/ or `nvm install 20` |
| npm | 10+ | Bundled with Node.js |
| Docker | 24+ | https://docs.docker.com/get-docker/ |
| Chrome | any | Required for headless test execution locally |
| Access to ADO project | — | Provided by platform team |

---

## Step 1 — Clone and run locally

```bash
git clone https://dev.azure.com/{ado-org}/{ado-project}/_git/{app-name}
cd {app-name}
npm install
npm start
```

Open http://localhost:4200 — you should see the Angular app.

---

## Step 2 — Run tests

```bash
# Interactive (watch mode, opens Chrome):
npx ng test

# Single pass (headless, same as CI):
npx ng test --watch=false --browsers=ChromeHeadless
```

Coverage reports land in `coverage/`.

---

## Step 3 — Production build

```bash
npm run build
# Output lands in dist/ (angular.json configures outputPath.browser: "")
```

---

## Step 4 — Build and run the Docker image locally

```bash
docker build -t {app-name}:local .
docker run --rm -p 80:80 {app-name}:local
```

Open http://localhost:80 — the nginx-served production build.

The Dockerfile copies from `dist/` directly into `/usr/share/nginx/html`. If your `angular.json` uses a nested output path, update the `COPY --from=build` line to match.

---

## Step 5 — Set the CONTAINER_IMAGE pipeline variable

1. In ADO, navigate to **Pipelines → {app-name} → Edit → Variables**
2. Add a variable named `CONTAINER_IMAGE` with value `myacr.azurecr.io/myorg/{app-name}`
3. Do not lock the variable (it is not a secret)

---

## Step 6 — Trigger the first pipeline run

Push a commit to `main` (or queue the pipeline manually in ADO).

Expected run sequence:

1. **Test stage** — `ng test` (headless Chrome); JUnit + Cobertura results in the **Tests** tab
2. **Build stage** — Docker build (runs `npm ci && npm run build` inside builder stage) + push
3. **image-meta artifact** — published under **Artifacts**

---

## Step 7 — Verify the config-repo trigger

After the build pipeline completes on `main`, check **Pipelines → {app-name}-k8s-manifests** — a new run should queue within ~60 seconds.

---

## Common first issues

| Symptom | Fix |
|---------|-----|
| `ng: command not found` | Run `npm install` first; use `npx ng` or add `./node_modules/.bin` to `PATH` |
| Tests fail with Chrome not found | Install Chrome; or use `npx ng test --browsers=ChromeHeadlessNoSandbox` |
| Docker `COPY --from=build /app/dist/` fails | Check `angular.json` `outputPath.browser` — it may produce a nested subdirectory |
| Pipeline test fails with no Chrome | The `ubuntu-latest` ADO agent has Chrome pre-installed; this usually self-resolves |
