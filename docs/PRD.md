# Product Requirements Document
## GitOps Tenant Onboarding Automation

**Status:** Proof of Concept — complete
**Scope:** Internal platform tooling

---

## Problem

Onboarding a new application team onto the platform requires a platform engineer to manually create and wire together a predictable set of Azure DevOps repositories, pipelines, Kubernetes manifests, and ArgoCD application definitions. This work is repetitive, error-prone, and does not scale as the number of tenants grows. The time between a team requesting platform access and having a working CI/CD pipeline is measured in days, not minutes.

---

## Goals

1. Reduce new tenant provisioning from a multi-day manual effort to a single pull request reviewed and merged by a platform operator.
2. Produce consistent, production-ready infrastructure artifacts for every tenant — no bespoke configuration per team.
3. Support phased onboarding: a team can request one application now and add more later without re-provisioning existing components.
4. Embed enough self-service capability in generated repositories that development teams can extend and operate their own pipelines without platform team involvement for routine changes.

---

## Users

**Platform Operator** — writes a YAML request file describing the tenant (name, apps, environments, resource tier), merges the PR that triggers generation, then runs the provisioning script once against Azure DevOps. This is the primary actor in the onboarding flow.

**Application Developer** — works within the generated repositories after onboarding completes. They do not interact with the onboarding tooling; they push code, review PRs, and approve deployment gates.

---

## Core Requirements

### Tenant definition
- A tenant is described by a single YAML request file committed to the onboarding repo and reviewed via PR before any generation occurs.
- The request file specifies: tenant identity (`tenant_slug`, ADO project/org), one or more applications (`name`, `type`, `container_image`), target environments, resource tier (`small` / `medium` / `large`), Key Vault name, ArgoCD revision, and optional Application Gateway configuration.
- Supported application types: Angular, React, Spring Boot, Go, Python, .NET.

### Generated artifacts — per application
Each application in the `apps` list produces three discrete ADO repositories:

| Repo | Contains |
|------|----------|
| `{name}` (build repo) | Language-appropriate Dockerfile, test pipeline, build pipeline via platform template, self-service agent skills |
| `{name}-k8s-manifests` (config repo) | Kustomize base (Deployment, HPA, VPA, PDB, ExternalSecret, ServiceAccount, Service) + per-environment overlays, promotion pipeline, self-service agent skills |
| `{name}-argocd` (ArgoCD repo) | Per-environment ArgoCD Application CRDs, emergency sync pipeline |

### CI/CD pipeline model
- **Build pipeline**: Test (language-native) → Docker build/push → publish `image-meta` artifact (image tag, SHA, build URL, git commit).
- **Config pipeline**: Triggered automatically by ADO pipeline resource when the build pipeline completes on `main`. Downloads `image-meta`, updates Kustomize overlay, opens PR. First environment (dev) has no approval gate and ArgoCD auto-sync. Subsequent environments require an ADO environment approval before ArgoCD sync.
- **Platform pipeline templates**: All shared stages and steps live in `platform-pipeline-templates`. No business logic is embedded in the templates; all tenant-specific values are explicit parameters.

### Provisioning
- `provision_tenant.py` drives the Azure DevOps REST API to create repos, push content, and register pipelines for only the components not already provisioned (`provisioned_components` in the request file).
- Idempotent: re-running the script against an existing tenant skips already-provisioned components and only processes the delta.
- The request file is the audit trail: successfully provisioned components are written back into `provisioned_components` using round-trip YAML to preserve comments.

### Self-service agent skills
Generated repositories ship with embedded Claude Code skills (`.agents/skills/`) covering the most common post-onboarding tasks development teams need:

- **Build repos**: `security-audit`, `upgrade-dependencies`, `add-healthcheck`, `multi-stage-dockerfile`, `grill-me`
- **Config repos**: `kustomize`, `tune-resources`, `add-probes`, `add-network-policy`, `add-ingress`, `grill-me`

---

## Out of Scope

The following are not automated and remain manual or pipeline-driven:

- ADO service connection creation (assumed pre-existing)
- Branch policy configuration per repo
- `kubectl apply` of ArgoCD Application CRDs to the cluster (handled by the argocd sync pipeline with human approval)
- ADO environment approval check wiring (operator configures in ADO portal post-provisioning)

---

## Success Criteria

- A platform operator can provision a new three-app tenant by editing one YAML file, merging one PR, and running one command.
- The generated build pipeline produces a pushed container image and triggers the config pipeline without manual intervention.
- An application developer can use the provided agent skills to add Kubernetes probes, tune resource limits, or run a security audit without requesting platform team support.
- Adding a new application to an existing tenant requires only editing the request file and re-running `provision_tenant.py`; existing repos and pipelines are untouched.
