# Iterative Onboarding

How to onboard a tenant in phases — App Gateway today, the build repo next
sprint, the config repo and ArgoCD app after that — using one request file
that accumulates an audit trail of what's been provisioned and when.

## The mechanism: `provisioned_components`

Every request file carries a field that isn't a Copier question at all —
Copier ignores it entirely when rendering, since it's not declared in
`copier.yml`. It exists purely for `provision_tenant.py`:

```yaml
provisioned_components:
- app_gateway
- build_repo
```

This is the record of what's already live in ADO. `provision_tenant.py`
compares it against `provisioning.yaml`'s `push_order` (which reflects
whatever `include_*` flags are currently `true`) and only acts on the
difference — components that are newly requested but not yet provisioned.
After a successful run, the script writes the newly-provisioned component
keys back into this list, in the request file, in place.

This was chosen over two alternatives — inferring state by querying ADO
directly, or a separate untracked CLI flag — specifically because the
request file already serves as your reviewed, PR-approved audit trail for
everything else about the tenant. Phase history belongs in the same place.

## Walkthrough: ACME onboarded across three PRs

This is the actual sequence used to build and test this mechanism, included
here with real output.

### PR #41 — App Gateway only

`onboarding-requests/tenant-acme-phased-history.yaml` starts like this:

```yaml
# PHASE 1 (PR #41): App Gateway only.
provisioned_components: []
include_app_gateway: true
include_build_repo: false
include_config_repo: false
include_argocd_app: false
```

`copier copy` renders only `app-gateway/`. `provision_tenant.py` runs:

```
Components already provisioned: (none)
Components to provision this run: ['app_gateway']
────────────────────────────────────────────────────────────
Component: app_gateway  →  repo: acme-app-gateway
────────────────────────────────────────────────────────────
  ✓ app_gateway provisioned successfully.

  ✓ Updated tenant-acme-phased-history.yaml — provisioned_components now: ['app_gateway']
```

The request file is rewritten with `provisioned_components: [app_gateway]`
— and critically, the `# PHASE 1 (PR #41)` comment survives the rewrite
(see "Comment preservation" below for why that's not automatic).

### PR #58 — adding the build and config repos, weeks later

The operator edits the same file, adds a new comment line, flips two flags:

```yaml
# PHASE 1 (PR #41): App Gateway only.
# PHASE 2 (this commit, PR #58): added build repo + config repo.
provisioned_components:
- app_gateway
include_app_gateway: true
include_build_repo: true      # ← changed
include_config_repo: true     # ← changed
include_argocd_app: false
```

Since the tenant directory already exists from PR #41, regeneration uses
`copier update` rather than `copier copy` — this preserves anything in
`app-gateway/` untouched (including any local customization) while adding
the newly-requested directories:

```bash
copier update --data-file tenant-acme-phased-history.yaml tenant-acme-phased
```

Result: `build-repo/` and `config-repo/` now exist; `app-gateway/` is
unchanged. `provisioning.yaml`'s `push_order` now lists all three.
`provision_tenant.py` run again:

```
Components already provisioned: ['app_gateway']
Components to provision this run: ['build_repo', 'config_repo']
────────────────────────────────────────────────────────────
Component: build_repo  →  repo: acme-build
────────────────────────────────────────────────────────────
  ✓ build_repo provisioned successfully.
────────────────────────────────────────────────────────────
Component: config_repo  →  repo: acme-config
────────────────────────────────────────────────────────────
  ✓ config_repo provisioned successfully.

  ✓ Updated tenant-acme-phased-history.yaml — provisioned_components now:
    ['app_gateway', 'build_repo', 'config_repo']
```

Note what did **not** happen: no repo-create call, no pipeline-create call,
nothing at all for `app_gateway` — it was correctly identified as already
done and skipped entirely.

### PR #67 — adding ArgoCD

Same pattern again: edit, flip `include_argocd_app: true`, `copier update`,
re-run the script. Only `argocd_app` gets provisioned; the other three are
skipped. `provisioned_components` ends at all four.

### Re-running with nothing new

If `provision_tenant.py` is run again with no new `include_*` flags
flipped, the delta is empty and the script does nothing:

```
Nothing to do — all requested components are already provisioned.
  provisioned_components: ['app_gateway', 'argocd_app', 'build_repo', 'config_repo']
```

This makes the script safe to run repeatedly or wire into a CI trigger on
every push to the onboarding-requests repo — it will only ever act on an
actual delta.

## What happens on partial failure

If a run provisions some components successfully and one fails (network
blip, ADO API error, a misconfigured service connection), only the
successful ones are written into `provisioned_components`. The script exits
non-zero and prints which components failed:

```
Provisioning run finished with failures: ['argocd_app']
Re-run the same command after addressing the error(s) above —
succeeded components will be skipped automatically.
```

Re-running the identical command after fixing the underlying issue will
correctly retry only the failed component, since the succeeded ones are
already recorded.

## Comment preservation

`provisioned_components` updates are written using `ruamel.yaml`'s
round-trip mode rather than plain `pyyaml`. This matters specifically
because the request file is meant to carry phase-by-phase PR references as
comments — a plain `yaml.safe_dump` rewrite would silently discard every
comment and reorder keys, which would defeat the audit-trail purpose this
mechanism exists for. `ruamel.yaml` preserves comments, key order, and most
blank-line structure through the load → mutate → dump cycle. One minor,
observed limitation: a blank line immediately following a mutated list can
occasionally be absorbed on rewrite — cosmetic only, doesn't affect data or
remaining comments.

## Operator workflow summary

1. Edit the tenant's request file: flip the next `include_*` flag(s) to
   `true`, add a comment noting the phase and PR number.
2. Open a PR. Get it reviewed and merged — this is the change-control gate
   for *which components get requested*, separate from the ADO pipeline
   approval gates that control *whether infrastructure changes actually
   apply*.
3. Run `copier update` (not `copier copy`, once the tenant directory
   already exists) against the merged request file.
4. Run `provision_tenant.py` — it will only act on the new delta.
5. The script commits the updated `provisioned_components` back into the
   request file automatically; commit and push that as a follow-up commit
   (or fold into the same PR if running before merge).

## Why not query ADO directly to infer what's already provisioned?

Considered and rejected for this design. Querying ADO for "does a repo
named `acme-build` already exist" can answer the repo-creation half of the
question, but doesn't equally clearly establish whether the pipeline,
environment, and approval check for that component were also fully wired —
some of these could exist in a partial state after an interrupted run.
`provisioned_components` is closer to a deliberate ledger: it's only
updated after `provision_tenant.py` confirms a component is fully done
(repo + push + pipeline + environments), which gives a clean either/or per
component rather than a fuzzy reconstruction from ADO's current state.
