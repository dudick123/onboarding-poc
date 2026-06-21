# Agent Skills — CI Config Repo

This repository ships with a set of Claude Code skills tailored to Kustomize manifest management and Kubernetes configuration tasks. Skills are stored in `.agents/skills/` and invoked from within Claude Code.

## How to use a skill

Open Claude Code in this repository and type `/skill-name`. Claude will read the skill definition and execute it against the current repo state.

```
# In Claude Code:
/kustomize
/tune-resources
/add-probes
/add-network-policy
/add-ingress
/grill-me
```

---

## Available skills

### `/kustomize`

**When to use:** As your primary reference when working with manifests in this repo. Also invoke it when you encounter unexpected behavior from `kustomize build`.

A comprehensive guide to the Kustomize patterns used in this repo: directory layout, `namePrefix` semantics, `images:` block ownership, `annotation-patch.yaml` pipeline ownership, and how to add resources and overlay patches without breaking existing resources. Includes a troubleshooting table for common errors.

---

### `/tune-resources`

**When to use:** When a workload is OOMKilled, CPU-throttled, or when the VPA has produced recommendations you want to act on.

Reviews `deployment.yaml`, `hpa.yaml`, and `vpa.yaml` against per-runtime baselines (Go, JVM, Node, Python, .NET). Flags anti-patterns: requests equal to limits, limits more than 4× requests, missing memory limits, HPA min-replicas below 2 in production. Produces diffs with reasoning for each change.

---

### `/add-probes`

**When to use:** When adding Kubernetes liveness and readiness probes to a workload that doesn't have them yet, or when the current probes have incorrect `initialDelaySeconds` for the runtime type.

Adds both `livenessProbe` and `readinessProbe` to the Deployment container spec with appropriate `initialDelaySeconds` per framework (JVM: 60–90s, Node/Go/Python: 20–30s, .NET: 40–60s). Uses `httpGet` against the `/health` endpoint. Shows the exact diff to `base/deployment.yaml`.

---

### `/add-network-policy`

**When to use:** When adding network-level isolation to restrict which pods can communicate with this workload.

Creates a `NetworkPolicy` manifest in `base/` that allows inbound traffic only from the ingress controller (on port 8080) and permits outbound DNS. Registers the policy in `base/kustomization.yaml`. Flags any additional egress rules you need to specify based on the application's known dependencies.

---

### `/add-ingress`

**When to use:** When the workload needs to be reachable from outside the cluster via HTTP/HTTPS.

Creates an `Ingress` resource in `base/` targeting the existing `Service`. Generates per-environment hostname patches for the overlays (e.g., `{app}-dev.tenant.example.com` vs. `{app}.tenant.example.com` for prod). Includes TLS secret reference. Shows the diff to all affected `kustomization.yaml` files.

---

### `/grill-me`

**When to use:** When you are about to make a significant change to the manifest structure — adding a new resource type, changing the namespace strategy, modifying HPA/VPA policy — and want to pressure-test the approach first.

Runs a relentless Socratic interview about your proposed change. Asks about cluster constraints, rollback strategy, impact on running pods, selector conflicts, and operational consequences. Useful for catching problems before opening a PR.

---

## Adding your own skills

Create a new directory under `.agents/skills/` with a `SKILL.md` file:

```
.agents/skills/
  my-skill/
    SKILL.md
```

The YAML front matter sets the skill name and description:

```markdown
---
name: my-skill
description: What this skill does.
---

Instructions for Claude to follow when this skill is invoked.
```

Invoke it with `/my-skill` in Claude Code.
