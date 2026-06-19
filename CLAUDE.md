# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo does

A proof-of-concept for automating tenant onboarding on a GitOps platform. An operator writes a YAML request file describing a tenant; Copier renders it into four component directories (App Gateway Terraform, container build repo, Kustomize config repo, ArgoCD Application); `provision_tenant.py` then drives the Azure DevOps REST API to create repos, push content, and register pipelines for only the components not already live.

## Setup

```bash
uv sync
```

Requires [uv](https://docs.astral.sh/uv/) and Python 3.9+. All dependencies (including Copier) are declared in `pyproject.toml` and pinned in `uv.lock`.

## Key commands

**Render a new tenant from a request file:**
```bash
uv run copier copy onboarding-template <tenant-dir> \
  --data-file onboarding-requests/<request>.yaml \
  --defaults --quiet
```

**Re-render an existing tenant after editing its request file (phased onboarding):**
```bash
uv run copier update --data-file onboarding-requests/<request>.yaml <tenant-dir>
```

**Provision (or incrementally add) the rendered components to Azure DevOps:**
```bash
uv run python provision_tenant.py \
  --tenant-dir ./generated-tenants/<tenant> \
  --request-file ./onboarding-requests/<request>.yaml \
  --ado-org https://dev.azure.com/my-org \
  --pat $ADO_PAT
```

`ADO_PAT` requires scopes: Code (Read & Write), Build (Read & Execute), Environment (Read & Manage).

## Architecture

### End-to-end flow

1. Operator writes a request YAML (committed and PR-reviewed)
2. `copier copy` renders component directories + `provisioning.yaml` from `onboarding-template/`
3. `provision_tenant.py` reads `provisioning.yaml` + request file, provisions only the delta (components in `push_order` not yet in `provisioned_components`), then writes newly-provisioned components back into the request file
4. ADO pipelines run; apply/sync stages are gated behind human approval

### Template structure (`onboarding-template/`)

- `copier.yml` — defines all questions; four boolean `include_*` toggles drive `_exclude` entries that entirely omit component directories when false. Component-specific follow-up questions use `when:` so they're never asked if the component is excluded.
- `{{tenant_slug}}/` directory naming — Copier resolves the variable in directory names at render time
- `provisioning.yaml.jinja` — rendered alongside components; maps each included component to its ADO repo name, pipeline YAML path, and approval environments. Guaranteed to stay in sync with the file tree because both come from the same render pass.

### Phased / iterative onboarding

The request file carries a `provisioned_components` list (ignored by Copier, read only by `provision_tenant.py`). To add a component later: flip its `include_*` to `true` in the request file, run `copier update` (not `copier copy`), then re-run `provision_tenant.py`. Only the new delta gets provisioned. The script writes successful components back into `provisioned_components` using `ruamel.yaml` round-trip mode to preserve comments and key order (the request file is the audit trail).

### `provision_tenant.py` internals

- `compute_delta()` — diffs `push_order` in `provisioning.yaml` against `provisioned_components` in request file
- `create_repo()` / `push_directory()` — uses `azure-devops` SDK typed clients; idempotent (409 → fetch existing)
- `create_pipeline()` — posts directly to ADO REST API via `requests` (not SDK) because the SDK's `CreatePipelineConfigurationParameters` doesn't expose typed `path`/`repository` fields
- `ensure_environment()` — creates ADO environments; approval checks must still be wired separately (Checks API not yet in Python SDK)
- `write_back_provisioned()` — uses `ruamel.yaml` to rewrite the request file preserving comments

### Known gaps (not built yet)

- Branch policy automation
- Service connection creation (pipelines assume they already exist)
- Actual `kubectl apply` of ArgoCD `application.yaml` to the cluster (that's the pipeline's job)
- `provision_tenant.py` has been exercised against mocked ADO clients only, not a live org

## Important Copier rules

- Use `_exclude` for conditional file inclusion — wrapping content in `{% if %}` produces an empty file, not a missing file
- Template must be referenced by absolute Git URL for `copier update` to resolve it reliably across machines
- `--data-file` values are typed per `copier.yml` question definitions; `--data` CLI flags override them
- The template directory must be a Git repo (`git init && git commit`) for `copier update` to work
