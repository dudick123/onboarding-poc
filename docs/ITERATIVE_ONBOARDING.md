# Iterative Onboarding

How to onboard a tenant in phases — starting with one application today and
adding more later — using one request file that accumulates an audit trail of
what's been provisioned and when.

## The mechanism: `provisioned_components`

Every request file carries a field that Copier ignores entirely when rendering
(it's not declared in `copier.yml`). It exists purely for `provision_tenant.py`:

```yaml
provisioned_components:
  - frontend_build
  - frontend_config
  - frontend_argocd
```

This is the record of what's already live in ADO. `provision_tenant.py`
compares it against `provisioning.yaml`'s `push_order` (which reflects the
current `apps` list and `include_app_gateway` flag) and only acts on the
difference — components that are newly generated but not yet provisioned.
After a successful run, the script writes the newly-provisioned component
keys back into this list, in the request file, in place.

Component keys are `{name_with_underscores}_build`, `{name_with_underscores}_config`,
and `{name_with_underscores}_argocd` per app (e.g., `orders_api_build` for
an app named `orders-api`), plus `app_gateway` if enabled.

This was chosen over querying ADO directly to infer state because `provisioned_components`
records a fully-completed component (repo + push + pipeline + environments) as
a clean binary. Querying ADO would give fuzzy partial-state answers after
interrupted runs. See "Why not query ADO directly" at the end of this document.

## Walkthrough: ACME onboarded across three PRs

### PR #1 — Frontend only, no App Gateway

The operator starts with just the `frontend` app to validate the platform
pipeline before committing to the full set.

```yaml
# onboarding-requests/tenant-acme-input.yaml
tenant_slug: acme
tenant_display_name: "ACME Industries"
ado_project: platform-tenants
ado_org_name: my-org
resource_tier: large
environments:
  - dev
  - staging
  - prod

apps:
  - name: frontend
    type: angular
    container_image: acr.azurecr.io/acme/frontend

key_vault_name: kv-acme-prod
argocd_target_revision: main
include_app_gateway: false

provisioned_components: []
```

Generate and provision:

```bash
uv run copier copy onboarding-template generated-tenants/tenant-acme \
  --data-file onboarding-requests/tenant-acme-input.yaml \
  --defaults --quiet

uv run python provision_tenant.py \
  --tenant-dir ./generated-tenants/tenant-acme \
  --request-file ./onboarding-requests/tenant-acme-input.yaml \
  --ado-org https://dev.azure.com/my-org \
  --pat $ADO_PAT
```

Output:

```
Components already provisioned: (none)
Components to provision this run: ['frontend_build', 'frontend_config', 'frontend_argocd']
────────────────────────────────────────────────────────────
Component: frontend_build  →  repo: frontend
────────────────────────────────────────────────────────────
  ✓ frontend_build provisioned successfully.
────────────────────────────────────────────────────────────
Component: frontend_config  →  repo: frontend-k8s-manifests
────────────────────────────────────────────────────────────
  ✓ frontend_config provisioned successfully.
────────────────────────────────────────────────────────────
Component: frontend_argocd  →  repo: frontend-argocd
────────────────────────────────────────────────────────────
  ✓ frontend_argocd provisioned successfully.

  ✓ Updated tenant-acme-input.yaml — provisioned_components now:
    ['frontend_argocd', 'frontend_build', 'frontend_config']
```

### PR #2 — Adding orders-api and inventory-api, weeks later

The operator edits the same request file, adds the two new apps, and notes
the phase:

```yaml
# PHASE 1 (PR #1): frontend only.
# PHASE 2 (this commit, PR #2): adding orders-api + inventory-api.
provisioned_components:
  - frontend_argocd
  - frontend_build
  - frontend_config

apps:
  - name: frontend
    type: angular
    container_image: acr.azurecr.io/acme/frontend
  - name: orders-api             # ← new
    type: springboot
    container_image: acr.azurecr.io/acme/orders-api
  - name: inventory-api          # ← new
    type: springboot
    container_image: acr.azurecr.io/acme/inventory-api
```

Since the tenant directory already exists from PR #1, use `copier update`
(not `copier copy`) — this preserves anything in `apps/frontend/` untouched
while adding the newly-declared app directories:

```bash
uv run copier update \
  --data-file onboarding-requests/tenant-acme-input.yaml \
  --defaults --quiet \
  generated-tenants/tenant-acme

uv run python provision_tenant.py \
  --tenant-dir ./generated-tenants/tenant-acme \
  --request-file ./onboarding-requests/tenant-acme-input.yaml \
  --ado-org https://dev.azure.com/my-org \
  --pat $ADO_PAT
```

Output:

```
Components already provisioned: ['frontend_argocd', 'frontend_build', 'frontend_config']
Components to provision this run: ['orders_api_build', 'orders_api_config',
                                   'orders_api_argocd', 'inventory_api_build',
                                   'inventory_api_config', 'inventory_api_argocd']
...
  ✓ Updated tenant-acme-input.yaml — provisioned_components now:
    ['frontend_argocd', 'frontend_build', 'frontend_config',
     'inventory_api_argocd', 'inventory_api_build', 'inventory_api_config',
     'orders_api_argocd', 'orders_api_build', 'orders_api_config']
```

Note what did **not** happen: no action for any `frontend_*` component — they
were correctly identified as already done and skipped entirely.

### PR #3 — Enabling App Gateway

Same pattern: edit the request file, set `include_app_gateway: true`, add the
required App Gateway fields, add a phase comment:

```yaml
# PHASE 3 (this commit, PR #3): enabling App Gateway.
include_app_gateway: true
app_gateway_backend_fqdn: acme-internal.svc.cluster.local
app_gateway_hostname: acme.platform.example.com
app_gateway_priority: 100
```

Run `copier update` (adds `app-gateway/` to the tenant directory), then
`provision_tenant.py` — only `app_gateway` gets provisioned; the nine
`{app}_*` components are skipped.

### Re-running with nothing new

If `provision_tenant.py` is run again with no new apps or flags:

```
Nothing to do — all requested components are already provisioned.
  provisioned_components: ['app_gateway', 'frontend_argocd', 'frontend_build',
                           'frontend_config', 'inventory_api_argocd', ...]
```

This makes the script safe to run on every push to the `onboarding-requests`
repo — it will only ever act on an actual delta.

## What happens on partial failure

If a run provisions some components successfully and one fails, only the
succeeded ones are written into `provisioned_components`. The script exits
non-zero:

```
Provisioning run finished with failures: ['orders_api_argocd']
Re-run the same command after addressing the error(s) above —
succeeded components will be skipped automatically.
```

Re-running after fixing the underlying issue retries only the failed
component.

## Comment preservation

`provisioned_components` updates are written using `ruamel.yaml`'s round-trip
mode rather than plain `pyyaml`. This preserves phase comments, key order, and
blank-line structure through the load → mutate → dump cycle. One minor,
observed limitation: a blank line immediately following a mutated list can
occasionally be absorbed on rewrite — cosmetic only, doesn't affect data or
remaining comments.

## Operator workflow summary

1. Edit the request file: add new apps to the `apps:` list (or flip
   `include_app_gateway: true`), add a comment noting the phase and PR number.
2. Open a PR. Get it reviewed and merged — this is the change-control gate
   for *which components get requested*, separate from the ADO pipeline
   approval gates that control *whether infrastructure changes actually apply*.
3. Run `copier update` (not `copier copy`, once the tenant directory already
   exists) against the merged request file.
4. Run `provision_tenant.py` — it acts only on the new delta.
5. The script updates `provisioned_components` in the request file automatically;
   commit and push that update as a follow-up commit.

## Recovery: regenerating a lost tenant directory

`copier update` requires `.copier-answers.yml` to exist in the local tenant
directory — it records which template version and answer set were used at
generation time. It is intentionally excluded from the ADO repo push, which
means it only lives in the local working directory where `copier copy` was
originally run.

If that directory is lost, the recovery procedure is:

1. Re-run `copier copy` against the same request file and the current template:
   ```bash
   uv run copier copy onboarding-template generated-tenants/tenant-acme \
     --data-file onboarding-requests/tenant-acme-input.yaml \
     --defaults --quiet
   ```
2. Any hand-edits made inside the ADO repos since initial provisioning will not
   be reflected in this fresh local copy. Pull the current ADO repo content into
   the local directory before running `copier update` if those edits matter.

The underlying design tension: `copier update` merges template changes against
the last-generated state (in `.copier-answers.yml`), but the ADO repo is the
canonical home of the actual files. A production workflow would keep the
generated tenant directory in a separate Git repo so `.copier-answers.yml`
is always recoverable from version control.

## Why not query ADO directly to infer what's already provisioned?

Querying ADO for "does a repo named `frontend` already exist" answers the
repo-creation half of the question, but doesn't establish whether the pipeline,
environment, and approval check for that component were also fully wired —
some of these could exist in partial state after an interrupted run.
`provisioned_components` is a deliberate ledger: it's only updated after
`provision_tenant.py` confirms a component is fully done (repo + push +
pipeline + environments), which gives a clean either/or per component rather
than a fuzzy reconstruction from ADO's current state.
