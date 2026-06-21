# Architecture

## End-to-end flow

```
1. Operator drafts a request file (YAML)
        ↓
2. Request file is reviewed via PR
        ↓
3. copier copy <template> <tenant-dir> --data-file <request.yaml>
   (or copier update, once the tenant directory already exists from
   an earlier phase — see docs/ITERATIVE_ONBOARDING.md)
        ↓
4. Output: component directories (only the ones requested) +
   provisioning.yaml (the ADO destination mapping for those components)
        ↓
5. provision_tenant.py reads provisioning.yaml + the request file:
   for each component in push_order NOT already in provisioned_components:
     - create ADO repo
     - push rendered content
     - register pipeline
     - ensure approval-gated environment exists
   then writes the newly-provisioned components back into the request
   file's provisioned_components field
        ↓
6. ADO pipelines run. Plan/build stages are automatic; apply/sync stages
   are gated behind a human approval (environment check), unchanged from
   the current operating model.
```

Steps 1–5 are built and demonstrated in this package, including the
phased/iterative case (request a component, provision it, later request
more — see `docs/ITERATIVE_ONBOARDING.md` for the full three-PR example).
Step 5's ADO API calls have been verified against mocked clients but not
yet against a live ADO organisation — see `docs/PROVISIONING.md` for what
to check before a first real run.

## Why Copier, and where its responsibility ends

Copier is a template-rendering tool. It clones a directory of Jinja2
templates, asks (or accepts via `--data-file`) a set of typed answers, and
writes out a concrete file tree. It has no concept of Git remotes, ADO
pipelines, Terraform state, or ArgoCD sync state. Its entire job in this
architecture is steps 3–4 above: turn an answer set into correct, internally
consistent files. Everything after that — repo creation, pipeline
registration, and especially anything that mutates real infrastructure
(`terraform apply`, `docker push`, `argocd app sync`) — is deliberately
outside Copier's scope and stays in ADO pipelines with human approval gates,
matching the existing operating model. This was a specific decision, not an
oversight: Copier doesn't need to know about Terraform or ArgoCD semantics
at all, which keeps the template simple and keeps the approval/change-control
process exactly where it already lives.

## Why one template repo with a post-generation task

The alternative — one Jinja template file per generated artifact — was
considered and rejected. The per-app directory tree (build-repo, config-repo,
argocd-app) is dynamic: it depends on the `apps:` list, which is operator-supplied
at generation time. Copier cannot natively iterate a list variable to produce
N copies of a directory. The solution is `_generate.py.jinja`: Copier renders
this file with tenant-level variables baked in, then the `_tasks` entry runs
it to create the full `apps/{name}/{build-repo,config-repo,argocd-app}/` tree
and self-deletes.

This means:
- One `copier.yml` holds the complete question set. `provisioning.yaml` is
  generated from the same answer set, guaranteeing the mapping can never drift
  from the directory structure that was actually written.
- A platform-wide change (e.g., adding a new base Kubernetes resource) is a
  single edit to `_generate.py.jinja`, not N edits across N template files.
- Existing files are never overwritten by the task script (`write_if_new` /
  `copy_exemplar_file` skip files that already exist), so `copier update` is
  safe to run on a tenant directory containing hand-edits.

## Why a generated `provisioning.yaml` rather than a hand-maintained mapping

The naming mapping (which component goes to which ADO repo name, which
pipeline name, which approval environment) needs `tenant_slug` and the
`include_*` answers already resolved — it can't live in `copier.yml` itself,
which is read before any answers exist. The two remaining options were a
hand-maintained YAML file the operator edits separately, or a third Jinja
template (`provisioning.yaml.jinja`) rendered from the same answers that
produce the component directories.

The generated approach was chosen because it guarantees the mapping can
never drift from the directory structure Copier actually wrote — if
`include_app_gateway` is false, `app_gateway` is absent from
`provisioning.yaml` in the same render pass that omits the `app-gateway/`
directory, by construction rather than by an operator remembering to keep
two files in sync.

## The request-file pattern (`--data-file`)

Copier supports `--data-file <path>` to load all answers from a YAML file
instead of either interactive prompts or a long string of `--data key=value`
flags. This is the mechanism behind the "operator input stored in Git"
requirement: a request file like `onboarding-requests/tenant-acme-input.yaml`
is a normal text file, reviewable in a PR, diffable, and usable as an audit
trail of who requested what and when.

Two details worth carrying into a real implementation:

- CLI `--data` flags take precedence over `--data-file` values if both are
  supplied, which is useful for one-off overrides during testing but
  shouldn't be relied on as a normal part of the workflow — the request
  file should be the single source of truth for a given tenant's answers.
- `--data-file` answers are typed according to each question's `type:` in
  `copier.yml`. A YAML list under `environments:` in the request file
  parses correctly as a list with no special syntax, which is part of why
  the request file is easier for a human to write correctly than the
  equivalent `--data` flags.

## Component selection mechanism

One boolean question in `copier.yml` controls conditional file inclusion:
`include_app_gateway`. When `false`, an `_exclude` entry removes the
`app-gateway/` directory entirely from the output — not as an empty directory,
but absent. Component-specific follow-up questions (`app_gateway_backend_fqdn`,
`app_gateway_hostname`, `app_gateway_priority`) use Copier's `when:` clause so
they are never asked when the component is not needed.

All three per-app repo types (build, config, argocd) are always generated for
every entry in the `apps:` list — there are no `include_build_repo` /
`include_config_repo` / `include_argocd_app` toggles. Adding or removing an
application is done by editing the `apps:` list and re-running `copier update`.

This was tested directly: a request with `include_app_gateway: false`
produces a tenant directory with no `app-gateway/` subdirectory at all, and
`provisioning.yaml`'s `components` and `push_order` correctly omit `app_gateway`.

## What's not built yet

**Branch policies.** Not addressed at all — whatever standard branch
policy set applies platform-wide (required PR, minimum reviewer count, etc.)
would need its own fixed payload applied per repo during provisioning,
separate from anything `provisioning.yaml` currently tracks.

**Service connections.** `provision_tenant.py` assumes an ADO service
connection for ACR, the Azure subscription, etc. already exists in the
project. It does not create service connections, and a pipeline that
references one that doesn't exist will fail at run time, not at
registration time.

**ArgoCD's actual cluster-side registration.** `argocd-app/application.yaml`
is pushed to its ADO repo by `provision_tenant.py`, but applying it to the
cluster (`kubectl apply`, or via ArgoCD's own API) happens in the
`argocd-sync` pipeline, gated behind human approval — exactly where it
lives today. `provision_tenant.py` never touches the cluster.

**Verification against a live ADO organisation.** Everything in
`provision_tenant.py` has been exercised against mocked ADO clients (see
`docs/PROVISIONING.md`), and bugs in the assumed SDK surface were found and
fixed this way — but it has not yet been run against a real org. Treat the
ADO API call shapes as "should be correct based on documentation and SDK
inspection," not "proven against production," until a first real dry run
confirms them.

## Known limitations worth carrying forward

- **Template references must be absolute** (a real ADO Git URL, not a local
  relative path) for `copier update` to reliably resolve the template later;
  this was hit directly while building earlier iterations of this POC.
- **`_exclude` is required for file-level conditionality; wrapping content
  in `{% if %}` only produces an empty file.** This was also hit directly
  while building the config-repo overlay logic and is why every
  conditionally-included piece in this template uses `_exclude` rather than
  in-file conditionals.
- **Secrets should use Copier's `secret: true` question flag** if any future
  question captures something sensitive (none currently do — Key Vault
  *names* are referenced, not credentials) so the value is excluded from
  `.copier-answers.yml`.
