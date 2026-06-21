# {app-name} — Kubernetes Config Repo

This is the **config repo** for `{app-name}` in the three-repo GitOps model. It holds Kustomize manifests for every environment and an ADO pipeline that promotes a built container image across environments.

## Role in the three-repo model

| Repo | Role |
|------|------|
| `{app-name}` (build repo) | Produces the container image |
| **This repo** (`{app-name}-k8s-manifests`) | Declares the desired Kubernetes state per environment |
| `{app-name}-argocd` | Applies the desired state to the cluster via ArgoCD |

This repo does not build code. It only describes **what should run** and **at what version**.

## What lives here

```
{app-name}/
  base/               ← shared manifests: Deployment, ServiceAccount, Service,
  │                     HPA, VPA, PodDisruptionBudget, ExternalSecret
  overlays/
    dev/              ← namespace, replica count, image tag (pipeline-managed)
    staging/
    prod/
azure-pipelines.yml   ← promotion pipeline (triggered by build pipeline)
```

## What the pipeline manages (do not edit by hand)

The ADO promotion pipeline overwrites these on every run:

- `overlays/{env}/kustomization.yaml` — `images[].newTag` field
- `overlays/{env}/annotation-patch.yaml` — image SHA, tag, timestamp, source pipeline URL

All other files are safe to edit. Changes merged to `main` are picked up by ArgoCD.

## Documentation

| Doc | What it covers |
|-----|----------------|
| [QUICK-START.md](QUICK-START.md) | Validate manifests locally, first-time orientation |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Kustomize model, pipeline flow, ArgoCD integration |
| [EXAMPLES.md](EXAMPLES.md) | How to add resources, patches, env vars, and labels |
| [AGENT-SKILLS.md](AGENT-SKILLS.md) | Available Claude Code skills and how to use them |

## Quick validation

```bash
# Validate all overlays
for env in dev staging prod; do
  echo "=== $env ===" && kustomize build {app-name}/overlays/$env
done
```
