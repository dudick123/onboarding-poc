# Provisioning: Moving Files to Azure DevOps

This document covers the second half of the onboarding flow — what happens
after `copier copy` has rendered the tenant directory.

## The two scripts

| Script | Purpose |
|---|---|
| `provision_tenant.py` | Main orchestrator — reads `provisioning.yaml`, drives all four ADO operations in `push_order` |
| `add_approval_check.py` | Adds a manual approval check to a named ADO environment — called by the main script, also runnable standalone |

## What each script actually does

### `provision_tenant.py`

Reads `provisioning.yaml` from the Copier-rendered tenant directory and
iterates `push_order`, performing four operations per component:

**1. Create the Git repository**

```python
git_client.create_repository(
    GitRepositoryCreateOptions(name=repo_name),
    project=project
)
```

POST to `_apis/git/repositories`. Returns a repo id and remote URL. The
script is idempotent — if a repo with the same name already exists (ADO
returns HTTP 409), it fetches the existing repo and continues rather than
failing.

**2. Push the rendered file tree as the initial commit**

The ADO Git REST API accepts an entire commit's worth of file content in
a single `POST _apis/git/repositories/{id}/pushes` call — no `git clone`,
no local git operations required. Every file under the component's
`source_dir` is read, encoded (UTF-8 text as `rawtext`, binary as
`base64Encoded`), and included as a `GitChange(change_type="add")` in one
atomic push. The `oldObjectId` for a brand-new repo's first push is always
the all-zeros SHA.

**3. Register the pipeline**

```python
build_client.create_definition(
    BuildDefinition(
        name=pipeline_name,
        repository=BuildRepository(id=repo.id, type="TfsGit", ...),
        process=YamlProcess(yaml_filename=pipeline_yaml_path),
    ),
    project=project
)
```

Points the pipeline at the `azure-pipelines.yml` that was just pushed into
the repo. Idempotent — checks for an existing definition with the same name
before creating.

**4. Create approval-gated environments**

For components that reference an ADO `environment:` approval gate in their
pipeline YAML (app-gateway, argocd-app), the environment must exist in ADO
before the pipeline first runs, or it will fail with "environment not found."
The script creates the environment via `task_client.add_environment()`, then
calls `add_approval_check.py`'s logic to wire the approval check.

### `add_approval_check.py`

The `azure-devops` Python SDK does not yet expose the Checks configuration
API (`_apis/pipelines/checks/configurations`). This script calls it
directly via `requests` with a `BasicAuthentication` PAT. It:

1. Resolves the environment name to a numeric id
2. Resolves each approver email to an AAD/MSA `subjectDescriptor` via the
   Graph API at `vssps.dev.azure.com`
3. POSTs the approval check body to the Checks API using the built-in
   approval check type id (`8c6f20a7-a545-4486-9777-f762fafe0d4d`), which
   is stable across ADO organisations

## Usage

```bash
# Required: set your PAT
export ADO_PAT=your-personal-access-token

# Run against the ACME tenant — only provisions components not yet in
# provisioned_components, and writes the result back to the request file
uv run python provision_tenant.py \
    --tenant-dir   ./generated-tenants/tenant-acme \
    --request-file ./onboarding-requests/tenant-acme-input.yaml \
    --ado-org      https://dev.azure.com/your-org \
    --pat          $ADO_PAT

# Or run the approval check standalone against an existing environment
uv run python add_approval_check.py \
    --ado-org    https://dev.azure.com/your-org \
    --project    platform-tenants \
    --env-name   app-gateway-acme-approval \
    --approvers  platform-lead@example.com,senior-eng@example.com \
    --pat        $ADO_PAT
```

See `docs/ITERATIVE_ONBOARDING.md` for the phased-onboarding workflow this
`--request-file` mechanism enables — requesting App Gateway today, the
build repo next sprint, and so on, with each run only acting on the delta.

## PAT scopes required

| Scope | Why |
|---|---|
| Code (Read & Write) | Create repos, push initial commit |
| Build (Read & Execute) | Register pipelines (`BuildDefinition`) |
| Environment (Read & Manage) | Create environments, add approval checks |
| Graph (Read) | Resolve approver email → AAD descriptor (used by `add_approval_check.py`) |

## Expected console output for a 4-component tenant

```
────────────────────────────────────────────────────
Component: build_repo  →  repo: acme-build
────────────────────────────────────────────────────
  ✓ Created repo: acme-build  (https://dev.azure.com/my-org/platform-tenants/_git/acme-build)
  ✓ Pushed 3 file(s) — commit a1b2c3d4
  ✓ Created pipeline: acme-build-push  (id=42)

────────────────────────────────────────────────────
Component: config_repo  →  repo: acme-config
────────────────────────────────────────────────────
  ✓ Created repo: acme-config
  ✓ Pushed 9 file(s) — commit e5f6a7b8
  ✓ Created pipeline: acme-kustomize-build  (id=43)

────────────────────────────────────────────────────
Component: app_gateway  →  repo: acme-app-gateway
────────────────────────────────────────────────────
  ✓ Created repo: acme-app-gateway
  ✓ Pushed 3 file(s) — commit c9d0e1f2
  ✓ Created pipeline: acme-app-gateway-plan-apply  (id=44)
  ✓ Created environment: app-gateway-acme-approval  (id=12)
  ✓ Approval check added to environment (check id=88)

────────────────────────────────────────────────────
Component: argocd_app  →  repo: acme-argocd
────────────────────────────────────────────────────
  ✓ Created repo: acme-argocd
  ✓ Pushed 2 file(s) — commit g3h4i5j6
  ✓ Created pipeline: acme-argocd-sync  (id=45)
  ✓ Created environment: argocd-sync-acme-approval  (id=13)
  ✓ Approval check added to environment (check id=89)

════════════════════════════════════════════════════
Provisioning complete.
════════════════════════════════════════════════════
```

## Testing status — what's been verified and how

`provision_tenant.py` has been run against **mocked** ADO clients (the
`azure.devops` SDK objects replaced with `unittest.mock` stand-ins), not a
live Azure DevOps organisation. This caught and fixed two real problems in
the original draft that static review alone hadn't caught:

- The pipeline-registration code originally used `BuildDefinition` /
  `YamlProcess` from the legacy Build Definitions API — `YamlProcess`
  doesn't exist in the installed SDK version at all. Pipeline registration
  now calls the modern Pipelines REST API (`POST _apis/pipelines`) directly
  via `requests`, since the SDK's own `CreatePipelineConfigurationParameters`
  model only types its `type` field as a bare `object` and doesn't reliably
  serialize the `path`/`repository` fields the live API needs.
- The git-push code referenced `GitChange`, which doesn't exist in this SDK
  version — the correct class name is `Change`.

Both were caught by attempting to import the script, not by reading SDK
documentation, which is itself a useful data point: **verify the actual
installed `azure-devops` SDK version's model names before relying on this
script**, since Microsoft has changed class names across versions and the
documentation doesn't always reflect the installed package.

The repo-creation, file-push, and environment-creation logic match the
documented REST API request/response shapes and the SDK model constructors
as installed, but none of it has executed against a real ADO org. Run a
single-component dry run (e.g., just `app_gateway` for a throwaway test
tenant) against a non-production ADO project before trusting this for real
onboarding.

## What the scripts do NOT handle

- **Branch policies** — minimum reviewer count, PR required, etc. These are
  a fixed, project-wide payload and could be applied per repo via
  `POST _apis/policy/configurations`, but are not wired up yet. Until added,
  apply branch policies via ADO portal or a separate policy script.
- **Service connections** — the pipelines assume an ADO service connection
  for ACR, Azure subscription, etc. already exists in the project. The
  scripts do not create service connections.
- **ArgoCD Application registration** — `argocd-app/application.yaml` is
  pushed to the ADO repo, but applying it to the cluster (via
  `kubectl apply` or ArgoCD's own API) is not done here. That's the step
  the `argocd-sync` pipeline handles after a human approves.
- **Existing tenants / `copier update` fan-out** — these scripts handle new
  tenant provisioning only. Rolling a template change out to existing tenants
  (clone, `copier update`, PR) is a separate loop not built yet.
