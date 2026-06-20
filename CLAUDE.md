# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo does

A proof-of-concept for automating tenant onboarding on a GitOps platform. An operator writes a YAML request file describing a tenant; Copier renders it into component directories and a `_generate.py` script; that script creates per-app discrete repo trees under `apps/`; `provision_tenant.py` then drives the Azure DevOps REST API to create repos, push content, and register pipelines for only the components not already live.

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

### Per-app discrete repo model

Each app in the `apps` list gets **three discrete ADO repos**:

| Repo name | Content | Source dir in tenant |
|-----------|---------|----------------------|
| `{name}` | Dockerfile + build pipeline | `apps/{name}/build-repo/` |
| `{name}-k8s-manifests` | Kustomize base + overlays + pipeline | `apps/{name}/config-repo/` |
| `{name}-argocd` | ArgoCD Application CRD + sync pipeline | `apps/{name}/argocd-app/` |

The app-gateway Terraform remains a single shared component (`{tenant_slug}-app-gateway`) when `include_app_gateway: true`.

### End-to-end flow

1. Operator writes a request YAML (committed and PR-reviewed)
2. `copier copy` renders `provisioning.yaml` + `_generate.py` from `onboarding-template/`
3. Copier's `_tasks` runs `python3 _generate.py && rm _generate.py`, which creates the full per-app directory tree under `apps/`
4. `provision_tenant.py` reads `provisioning.yaml` + request file, provisions only the delta (components in `push_order` not yet in `provisioned_components`), then writes newly-provisioned components back into the request file
5. ADO pipelines run; ArgoCD sync stages are gated behind human approval per app

### Template structure (`onboarding-template/`)

- `copier.yml` — defines all questions. Core identity: `tenant_slug` (validated `^[a-z][a-z0-9-]{1,28}$`), `ado_project`, `ado_org_name`, `resource_tier`, `environments`. App list: `apps` (type: yaml, list of `{name, type, container_image}`; supported types: angular, react, springboot, go, python, dotnet). Tenant-wide settings: `key_vault_name`, `argocd_target_revision`. Optional: `include_app_gateway` toggle + `app_gateway_*` follow-up questions. No `include_build_repo / include_config_repo / include_argocd_app` flags — these are always generated for every app.
- `_generate.py.jinja` — Copier renders this file with tenant-level Jinja2 variables baked in (`tenant_slug`, `apps | tojson`, `environments | tojson`, etc.), then the `_tasks` entry runs it to create the full `apps/{name}/{build-repo,config-repo,argocd-app}/` tree. Dockerfiles and all other files are only written if they don't already exist (safe for `copier update`). Self-deletes after running.
- `provisioning.yaml.jinja` — loops over `apps` to generate one `{name}_build`, `{name}_config`, `{name}_argocd` component entry per app, plus `app_gateway` if enabled. The `push_order` list follows the same pattern. Guaranteed in sync with `_generate.py`'s output because both come from the same `apps` list.
- `app-gateway/` — Terraform for Application Gateway listener (excluded when `include_app_gateway: false`).

### Phased / iterative onboarding

The request file carries a `provisioned_components` list (ignored by Copier, read only by `provision_tenant.py`). To add a new app later: add it to the `apps` list in the request file, run `copier update` (not `copier copy`), then re-run `provision_tenant.py`. Only the new delta gets provisioned. The script writes successful components back into `provisioned_components` using `ruamel.yaml` round-trip mode to preserve comments and key order (the request file is the audit trail).

### `provision_tenant.py` internals

- `compute_delta()` — diffs `push_order` in `provisioning.yaml` against `provisioned_components` in request file
- `create_repo()` / `push_directory()` — uses `azure-devops` SDK typed clients; idempotent (409 → fetch existing)
- `create_pipeline()` — posts directly to ADO REST API via `requests` (not SDK) because the SDK's `CreatePipelineConfigurationParameters` doesn't expose typed `path`/`repository` fields; uses `?name=` server-side filter for idempotent lookup
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
- `_envops: trim_blocks: true, lstrip_blocks: true` is set globally; avoid Jinja2 block tags (`{% %}`) in Python task scripts to prevent whitespace stripping surprises
