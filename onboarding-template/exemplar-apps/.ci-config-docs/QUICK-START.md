# CI Config Repo — Quick Start

## Prerequisites

- [kustomize](https://kubectl.docs.kubernetes.io/installation/kustomize/) CLI (v5+)
- Access to the ADO project containing this repo
- Familiarity with Kubernetes YAML (helpful, not required for most tasks)

---

## Step 1 — Understand the repo structure

```
{app-name}/
  base/
    kustomization.yaml    ← resource list + commonLabels
    deployment.yaml       ← Deployment with resource requests/limits
    serviceaccount.yaml
    service.yaml          ← ClusterIP on port 8080
    hpa.yaml              ← HorizontalPodAutoscaler (autoscaling/v2)
    vpa.yaml              ← VerticalPodAutoscaler (recommendation mode)
    pdb.yaml              ← PodDisruptionBudget (maxUnavailable: 1)
    external-secret.yaml  ← ExternalSecret pulling from Azure Key Vault
  overlays/
    dev/
      kustomization.yaml    ← namespace, namePrefix, replicas, image tag
      annotation-patch.yaml ← pipeline-owned: SHA, tag, timestamp
    staging/
      ...
    prod/
      ...
```

**Key rules:**
- `base/` declares the canonical shape of the workload. Edit here when a change applies to all environments.
- `overlays/{env}/` declares per-environment differences. Edit here when only one environment changes.
- `annotation-patch.yaml` is overwritten on every pipeline run — do not edit it.

---

## Step 2 — Validate manifests locally

Before opening a PR, always confirm the Kustomize build succeeds:

```bash
# Validate a single overlay
kustomize build {app-name}/overlays/dev

# Validate all overlays
for env in dev staging prod; do
  echo "=== $env ===" && kustomize build {app-name}/overlays/$env || exit 1
done
```

A successful build prints the full set of Kubernetes resources to stdout. Pipe to a file to review the complete rendered output:

```bash
kustomize build {app-name}/overlays/prod > /tmp/prod-manifests.yaml
```

---

## Step 3 — Understand what the pipeline changes

On each run the promotion pipeline:

1. Downloads `image-meta.json` from the build pipeline artifact
2. Runs `kustomize edit set image {container-image}:{build-id}` in the overlay directory
3. Overwrites `annotation-patch.yaml` with:
   - `platform.io/image-sha` — registry digest (`sha256:...`)
   - `platform.io/image-tag` — build ID
   - `platform.io/promoted-at` — RFC3339 timestamp
   - `platform.io/source-pipeline` — ADO build URL
4. Runs `kustomize build` to validate
5. Pushes a branch and opens a PR

For the **first environment** (dev): the PR is auto-merged and ArgoCD syncs automatically.

For **subsequent environments** (staging, prod): the pipeline waits for an ADO environment approval before syncing ArgoCD.

---

## Step 4 — Make your first change

The most common first change is adding a label to all resources.

1. Edit `{app-name}/base/kustomization.yaml`, add to `commonLabels`:

```yaml
commonLabels:
  app.kubernetes.io/part-of: my-tenant
  app.kubernetes.io/name: {app-name}
  platform.io/tenant: my-tenant
  platform.io/tier: medium
  my-team/owner: my-team-name    # ← new label
```

2. Validate:

```bash
kustomize build {app-name}/overlays/dev | grep "my-team/owner"
```

3. Open a PR. After merge, ArgoCD picks up the change on the next sync cycle.

---

## Step 5 — Understand what ArgoCD does with this repo

The `{app-name}-argocd` repo contains an `Application` CRD per environment. Each Application points to a specific overlay path in this repo:

```yaml
source:
  path: {app-name}/overlays/dev
```

ArgoCD watches this path and syncs when it detects drift. For `dev`, sync is automated. For `staging` and `prod`, sync is triggered by the ADO config pipeline after an approval gate.

You do not need to interact with ArgoCD directly for normal promotions.

---

## Common first questions

**Q: The pipeline ran but the overlay didn't update — what happened?**
The config pipeline only triggers when the build pipeline completes on `main`. Check that the build pipeline succeeded and that the pipeline resource trigger is configured correctly in `azure-pipelines.yml`.

**Q: I want to change the number of replicas — where do I do that?**
In the overlay's `kustomization.yaml` under the `replicas:` block — not in `base/deployment.yaml`. See [EXAMPLES.md](EXAMPLES.md).

**Q: What is `namePrefix: {env}-` doing?**
Every resource name is prefixed with the environment name at render time. The base name in `base/deployment.yaml` is `{app-name}`; in dev it becomes `dev-{app-name}`. Reference the base name (without prefix) in any patches you write.

**Q: Why does `annotation-patch.yaml` have all `pending` values?**
`pending` is the initial placeholder. The pipeline overwrites these on its first run. Until the pipeline has run at least once for an environment, these annotations reflect the unprovisioned state.
