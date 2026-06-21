# Quick Start — Go Build Repo

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Go | 1.22+ | https://go.dev/dl/ |
| Docker | 24+ | https://docs.docker.com/get-docker/ |
| Access to ADO project | — | Provided by platform team |

---

## Step 1 — Clone and run locally

```bash
git clone https://dev.azure.com/{ado-org}/{ado-project}/_git/{app-name}
cd {app-name}
go run .
```

Open http://localhost:8080 — you should see `{"message":"Hello, World!"}`.
Open http://localhost:8080/health — you should see `{"status":"ok"}`.

---

## Step 2 — Run tests

```bash
go test ./...
```

Expected output: `ok  {module-name}  0.XXXs`

With coverage:

```bash
go test -coverprofile=coverage.out ./...
go tool cover -func=coverage.out
```

---

## Step 3 — Build and run the Docker image locally

```bash
docker build -t {app-name}:local .
docker run --rm -p 8080:8080 {app-name}:local
```

Test that the containerized app behaves the same as the local run:

```bash
curl http://localhost:8080/health
# {"status":"ok"}
```

---

## Step 4 — Set the CONTAINER_IMAGE pipeline variable

The pipeline cannot push an image without knowing where to push it.

1. In ADO, navigate to **Pipelines → {app-name} → Edit → Variables**
2. Add a variable named `CONTAINER_IMAGE` with value `myacr.azurecr.io/myorg/{app-name}`
3. Do not lock the variable (it is not a secret)

The value must be a full registry path **without** a tag. Tags are appended automatically by the pipeline (`$(Build.BuildId)` and `latest`).

---

## Step 5 — Trigger the first pipeline run

Push a commit to `main` (or queue the pipeline manually in ADO).

Expected run sequence:

1. **Test stage** — `go test ./...` runs; results appear in the **Tests** tab
2. **Build stage** — Docker build + push; image lands in the registry with tags `$(Build.BuildId)` and `latest`
3. **image-meta artifact** — published; visible under **Artifacts** in the run summary

---

## Step 6 — Verify the config-repo trigger

After the build pipeline completes on `main`, the `{app-name}-k8s-manifests` config pipeline should queue automatically within ~60 seconds. Check:

**Pipelines → {app-name}-k8s-manifests** — you should see a new run queued with "triggered by build pipeline".

If it does not appear, verify that the pipeline resource trigger is configured correctly in `{app-name}-k8s-manifests/azure-pipelines.yml`.

---

## Common first issues

| Symptom | Fix |
|---------|-----|
| `go: cannot find main module` | `go.mod` is missing or you are not in the repo root |
| Pipeline fails at Docker push with auth error | Service connection for the container registry is not configured in ADO; raise with platform team |
| `CONTAINER_IMAGE` still shows `REPLACE_WITH_YOUR_REGISTRY_AND_IMAGE` | The variable was not saved in Pipeline Settings, or the pipeline YAML value is overriding it |
| Config-repo pipeline does not trigger | Check that the pipeline resource trigger in the config repo's `azure-pipelines.yml` matches this pipeline's name exactly |
