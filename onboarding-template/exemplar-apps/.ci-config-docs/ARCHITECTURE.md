# CI Config Pipeline — Architecture

This repository is the **config repo** in a three-repo GitOps model. It holds Kustomize manifests and drives image promotion across environments using an ADO pipeline triggered by the upstream build pipeline.

## Three-repo model

```
[build repo]          [config repo]             [argocd repo]
{app-name}    ──►    {app-name}-k8s-manifests   {app-name}-argocd
  (this run           (this repo)                  (ArgoCD CRDs)
   produces
   image-meta
   artifact)
```

## Kustomize base/overlay model

```
{app-name}/
  base/             ← canonical resource definitions (all environments share this)
  overlays/
    dev/            ← namespace: {tenant}-dev,  namePrefix: dev-,  replicas: 1
    staging/        ← namespace: {tenant}-staging, namePrefix: staging-, replicas: 1
    prod/           ← namespace: {tenant}-prod, namePrefix: prod-, replicas: N
```

### Base resources

| File | Resource | Notes |
|------|----------|-------|
| `deployment.yaml` | Deployment | `serviceAccountName` set; `envFrom` pulls `{tenant}-secrets` |
| `serviceaccount.yaml` | ServiceAccount | One per app; used for IRSA/Workload Identity |
| `service.yaml` | Service (ClusterIP) | Port 8080 → 8080 |
| `hpa.yaml` | HorizontalPodAutoscaler | `autoscaling/v2`; CPU 70%, memory 80% |
| `vpa.yaml` | VerticalPodAutoscaler | `updateMode: Off` (recommendation only, not auto-applied) |
| `pdb.yaml` | PodDisruptionBudget | `maxUnavailable: 1` |
| `external-secret.yaml` | ExternalSecret | Pulls all secrets for this tenant from Azure Key Vault |

### Overlay anatomy

```yaml
# overlays/prod/kustomization.yaml
namespace: {tenant}-prod      # overrides base namespace
namePrefix: prod-             # prepended to every resource name
replicas:
  - name: {app-name}
    count: 2                  # prod gets more replicas than dev
images:
  - name: {container-image}
    newTag: pending           # ← pipeline writes the real build ID here
patches:
  - path: annotation-patch.yaml   # ← pipeline writes SHA + metadata here
```

### `namePrefix` semantics

Every resource gains the `{env}-` prefix at render time. A `Deployment` named `{app-name}` in base becomes `prod-{app-name}` in the prod overlay output. When writing patches, always reference the **base name** — Kustomize applies the prefix automatically.

## Promotion pipeline flow

```
Build pipeline completes on main
         │
         ▼
ADO pipeline resource trigger fires
         │
         ▼
Download image-meta artifact
  { containerImage, imageTag, imageSha, buildId, buildUrl, gitCommit, builtAt }
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  For each environment in order:                             │
│                                                             │
│  1. kustomize edit set image {image}:{tag}                  │
│  2. Overwrite annotation-patch.yaml with SHA + metadata     │
│  3. kustomize build (validate)                              │
│  4. git commit + push branch                                │
│  5. Create PR (autoComplete: squash merge)                  │
│                                                             │
│  First env (dev): regular job, no approval gate             │
│  Subsequent envs: deployment job, ADO environment gate      │
│  After approval: argocd app sync                            │
└─────────────────────────────────────────────────────────────┘
```

### ADO environment approval gates

For non-first environments, the pipeline uses an ADO `deployment:` job type targeting:

```
config-promote-{tenant}-{app-name}-{env}-approval
```

An operator must configure the **Approvals and checks** on this ADO Environment in the ADO portal. The pipeline waits for approval before proceeding to ArgoCD sync.

## Per-environment ArgoCD control planes

Each environment has its own ArgoCD control plane with a unique FQDN. The pipeline reads the server and token from the `argocd-servers` variable group:

| Variable | Example value |
|----------|---------------|
| `ARGOCD_SERVER_DEV` | `argocd.dev.platform.example.com` |
| `ARGOCD_SERVER_STAGING` | `argocd.staging.platform.example.com` |
| `ARGOCD_SERVER_PROD` | `argocd.prod.platform.example.com` |
| `ARGOCD_TOKEN_DEV` | (secret) |
| `ARGOCD_TOKEN_STAGING` | (secret) |
| `ARGOCD_TOKEN_PROD` | (secret) |

The ArgoCD Application CRD in `{app-name}-argocd/{env}/application.yaml` points ArgoCD at the overlay path for that environment. ArgoCD continuously reconciles the cluster state against the overlay output.

## Annotation tracking

`annotation-patch.yaml` provides deployment provenance on every running Pod:

```yaml
annotations:
  platform.io/image-sha: "sha256:abc123..."    # registry digest (immutable)
  platform.io/image-tag: "456"                 # build ID from build pipeline
  platform.io/promoted-at: "2024-01-15T10:30:00Z"
  platform.io/source-pipeline: "https://dev.azure.com/.../builds/456"
```

These annotations survive across `kubectl rollout restart` calls and make it trivial to trace any running pod back to the exact build that produced it.

## What triggers a re-sync vs. a re-promotion

| Scenario | What happens |
|----------|-------------|
| New build pipeline run on `main` | Full re-promotion: image tag updated, PR opened, approval required |
| Manual edit to `base/` or overlay merged to `main` | ArgoCD detects drift and syncs (dev: automatic; others: manual or via argocd-app sync pipeline) |
| ArgoCD `selfHeal: true` drift correction (dev only) | ArgoCD reverts manual cluster changes back to the manifest state |
| Rollback needed | Open a PR manually to revert the image tag in the overlay, or use the `{app-name}-argocd` sync pipeline to force-sync a previous overlay revision |
