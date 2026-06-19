# Phase 1 Review

Senior Python / Copier review of the current proof-of-concept. Written against the code and templates as they exist in this repository.

---

## Overall verdict

The architectural core is sound. The decision to use Copier for file generation, separate provisioning from rendering, keep approval gates in ADO pipelines, and treat the request file as a PR-reviewed audit trail are all good calls that will hold up at scale. The phased-onboarding mechanism via `provisioned_components` is well-designed and the `ruamel.yaml` round-trip rewrite that preserves comments is exactly the right choice for that use case.

That said, there are concrete bugs in the templates, a few significant gaps in the provisioning script, and several Copier anti-patterns that need to be fixed before this is usable beyond a single demo tenant. The issues are enumerated below in order of severity.

---

## What works well

- **`provisioning.yaml.jinja` is the standout design decision.** Generating the ADO mapping from the same answer set that produces the file tree means the two can never drift. This avoids an entire class of human error.
- **`_exclude` for conditional components is correct.** Using `_exclude` with templated entries (rather than in-file `{% if %}` guards) is the right Copier pattern. The alternative was directly tested and documented as a gotcha.
- **`provisioned_components` as an in-file ledger is the right call over ADO state inference.** Querying ADO to reconstruct "what's been provisioned" would give fuzzy partial-state answers; an explicit audit field gives a clean binary per component.
- **Error handling in `provision_tenant.py` is correct.** Partial failures record only the succeeded components, which makes re-runs safe and predictable.
- **`ruamel.yaml` for request file rewriting** is the right choice. Plain `pyyaml` would silently discard every comment and reorder keys, which would destroy the audit trail the request file exists to provide.
- **`push_order` is explicit and well-reasoned.** The ordering comment (`build_repo` and `config_repo` before `argocd_app`) is correct and the ordering is enforced, not assumed.

---

## Issues

### Critical — will break in real use

**1. App Gateway routing rule priority is hardcoded to `100`**

`main.tf.jinja`:

```hcl
priority = 100
```

Every tenant gets `priority = 100`. On a shared Application Gateway, the second tenant's `terraform apply` will fail because routing rule priorities must be unique per gateway. Priority needs to be a required input question in `copier.yml` (e.g., `app_gateway_priority: int`) and rendered as a variable.

---

**2. ArgoCD `repoURL` is missing the ADO organisation name**

`argocd-app/application.yaml.jinja`:

```yaml
repoURL: https://dev.azure.com/{{ ado_project }}/_git/{{ tenant_slug }}-config
```

The correct ADO Git URL format is `https://dev.azure.com/{org}/{project}/_git/{repo}`. The organisation name is absent. This will produce a broken `application.yaml` for every tenant. An `ado_org_name` question (or a convention to derive it from `ado_project`) needs to be added.

---

**3. Kustomize overlays use the deprecated `bases:` field**

All three overlay `kustomization.yaml.jinja` templates use:

```yaml
bases:
  - ../../base
```

`bases:` was deprecated in `kustomize.config.k8s.io/v1beta1` and removed in later Kustomize versions. It must be replaced with `resources:`. Running `kustomize build` on the generated output will produce warnings (and errors on newer installs).

---

**4. `push_directory` is not idempotent for non-empty repos**

`provision_tenant.py` `push_directory()` hard-codes `old_object_id = "0000000000000000000000000000000000000000"`, which the ADO API only accepts for a first push to an empty repository. If a repo was created but the push failed mid-run (e.g., network drop), the repo is non-empty and a re-run will fail with a 409 or 422 that is not caught. The `create_repo` call handles the "repo already exists" case, but `push_directory` does not handle the "repo already has commits" case. The idempotency gap here means a partial failure on the push step leaves the component in an unrecoverable state without manual ADO intervention.

---

### Important — will cause bugs or maintenance problems

#### 5. Overlay replica logic uses tautological string comparisons

`overlays/dev/kustomization.yaml.jinja`:

```jinja
count: {% if "dev" == "prod" %}...{% else %}1{% endif %}
```

`"dev" == "prod"` is always `False`, so `dev` and `staging` overlays always render `count: 1` regardless of `resource_tier`. The `prod` overlay has `"prod" == "prod"` which is always `True`. The intent was clearly to vary replica count by environment, but the templates hardcode the environment name as a string literal rather than using a variable. The three overlay files have nearly identical logic with a single string changed, which means they will drift as the template evolves. The tier-based replica specs should live in one place (a `set` block in the base deployment template, or as a Copier variable) and the overlays should reference it.

---

**6. No `validator:` on `tenant_slug`**

`copier.yml` declares `tenant_slug` as a bare `type: str` with no pattern constraint. An invalid slug — uppercase letters, spaces, dots, or leading digits — will silently produce:

- Invalid Kubernetes namespace names (which reject uppercase and must start with a letter)
- Invalid ADO repo names
- Potentially broken Terraform resource names

A `validator:` entry with a regex (`^[a-z][a-z0-9-]{1,28}$` or similar) needs to be added. Kubernetes namespace names have a 63-character limit; ADO repo names have different rules. Pick the most restrictive common denominator.

---

#### 7. Dockerfile is Java/JVM-specific with no question to select runtime

`build-repo/Dockerfile.jinja`:

```dockerfile
FROM eclipse-temurin:21-jre-alpine
ENTRYPOINT ["java", "-jar", "app.jar"]
```

The template presents as a general-purpose platform onboarding tool, but the Dockerfile assumes a JVM application. A tenant running a Go service, a Python worker, or a Node.js app will get a silently wrong Dockerfile. Either add a `runtime` question to `copier.yml` (with choices: `java`, `go`, `python`, `node`, `custom`) with conditional Dockerfile templates per runtime, or clearly scope the template to JVM services and document that limitation prominently.

---

**8. `create_pipeline` idempotency check does not handle pagination**

```python
resp = requests.get(list_url, params={"api-version": "7.1"}, ...)
if any(p["name"] == pipeline_name for p in resp.json().get("value", [])):
```

The ADO Pipelines list API is paginated. On an organisation with more than the default page size of pipelines, this check will miss existing pipelines beyond the first page and silently create a duplicate. The check needs to follow `continuationToken` or use a server-side `name` filter parameter (`?name={pipeline_name}`).

---

**9. PAT leaks to process list when passed as `--pat`**

`provision_tenant.py` accepts the PAT as a CLI argument, which puts it in `/proc/{pid}/cmdline` and `ps aux` output, readable by any user on the machine. The env var path (`ADO_PAT`) is safe; the `--pat` path is not. The argument should either be removed (env var only) or replaced with a path to a file containing the token. At minimum, add a warning to the help text.

---

**10. `add_approval_check.py` fetches all Graph users for email resolution**

`get_user_descriptor` calls `GET _apis/graph/users` without filtering, then linearly searches the result for a matching email. On a large organisation, this returns thousands of users across multiple pages (no pagination handling is present) or may be throttled. The Graph API does not support email-based filtering directly, but there are alternative approaches: `GET _apis/identities?searchFilter=General&filterValue={email}` or the `identityPicker` API. This is slow and fragile as written.

---

**11. `.copier-answers.yml` is excluded from ADO push but required for `copier update`**

`provision_tenant.py` explicitly skips `.copier-answers.yml` when building the push payload:

```python
if file_path.name == ".copier-answers.yml":
    continue
```

This is correct for keeping Copier bookkeeping out of the ADO repo. However, `copier update` requires the `.copier-answers.yml` file to exist in the generated tenant directory to know what answers were used and what template version was last applied. If the local tenant directory is lost (machine wipe, new developer), `copier update` cannot be run and the only recovery is `copier copy` (which re-renders from scratch, losing any local customisation). This workflow gap needs a documented recovery procedure, and the question of where the generated directory's `.copier-answers.yml` lives long-term needs an answer before production use.

---

### Minor — polish and correctness issues

**12. `base/deployment.yaml.jinja` uses `:latest`**

```yaml
image: {{ container_image }}:latest
```

The Kustomize overlays correctly override the tag per environment (`newTag: dev`, `newTag: prod`), so this won't reach production as-is. But `:latest` in the base is a bad practice and will cause confusion: any tool that processes only the base (e.g., security scanners, linters) will see `:latest` rather than a real tag.

#### 13. QUICKSTART.md section 5 is stale

Section 5 "Push to Azure DevOps" says "(Not included yet)" but `provision_tenant.py` now exists and is documented in `PROVISIONING.md`. The quickstart should either describe how to run it or link to `PROVISIONING.md` instead of treating it as future work.

**14. `provisioned_components` is written sorted alphabetically, not in `push_order`**

```python
data["provisioned_components"] = sorted(current)
```

The alphabetical sort means `provisioned_components` reads `['app_gateway', 'argocd_app', 'build_repo', 'config_repo']` — alphabetical, not in the dependency order that `push_order` declares. This is cosmetically inconsistent (and could confuse someone reading the file who expects an ordered audit trail) but has no functional impact since `compute_delta` only checks set membership.

**15. No `.gitignore`**

The repository has no `.gitignore`. Running `uv sync` creates a `.venv/` directory, and local `copier copy` experiments produce tenant directories (e.g., `tenant-acme/`, `tenant-internalbatch/`) that can end up tracked accidentally. At minimum: `.venv/`, `__pycache__/`, `*.pyc`, and patterns matching ad-hoc local tenant directories should be excluded.

**16. `generated-tenants/` committed alongside templates**

Committing generated output to the same repo as the template that produces it blurs the separation of concerns and makes `git log` noisy. In production the generated tenant directories should each live in their own ADO repo. For this POC it's acceptable but should be called out explicitly so it isn't cargo-culted into the real implementation.

---

## Copier-specific assessment

The template's Copier usage is mostly correct. A few observations from a Copier-first perspective:

- **`_envops` configuration is correct.** `trim_blocks: true` and `lstrip_blocks: true` are the right settings for YAML-generating templates where extra blank lines from block tags would break the output.
- **`type: yaml` for `environments` works but is unusual.** It requires the operator to write a YAML list inline in the request file. Since `copier.yml` supports `type: str` with choices or multi-select, consider whether a comma-separated string with a custom type or a choices-based question would be more operator-friendly.
- **`when:` clauses are used correctly.** Conditional follow-up questions (`app_gateway_backend_fqdn` only when `include_app_gateway`) match the `_exclude` conditions exactly, which is the right approach.
- **Missing `validator:` entries throughout.** None of the string questions validate input. Beyond `tenant_slug` (critical), `ado_project`, `container_image`, and `app_gateway_hostname` would all benefit from basic format checks.
- **No `placeholder:` or `help_text:` on most questions.** The `help:` strings are present but `placeholder:` (shown in the interactive prompt) would reduce errors for first-time operators. For example, `container_image` could show `acr.azurecr.io/your-tenant/service-name` as a placeholder.
- **The answers file template is correct** (`{{_copier_conf.answers_file}}.jinja`). This ensures the answers file name is controlled by Copier's configuration rather than hardcoded, which is the idiomatic approach.

---

## Recommended priorities for Phase 2

All 11 items below were identified during Phase 1 review and subsequently implemented.

1. Fix the App Gateway priority collision — added `app_gateway_priority` question to `copier.yml`; `main.tf.jinja` now renders `var.app_gateway_priority`
2. Fix the ArgoCD `repoURL` — added `ado_org_name` question; URL now includes org segment
3. Replace `bases:` with `resources:` in all Kustomize overlays — fixed in templates and all generated files
4. Add `validator:` to `tenant_slug` in `copier.yml` — enforces `^[a-z][a-z0-9-]{1,28}$`
5. Fix overlay replica logic — each overlay now sets `{% set overlay_env = "..." %}` and uses it in the count expression
6. Dockerfile runtime question — added `runtime` question (java/python/go/node) with per-runtime template blocks
7. Address `.copier-answers.yml` persistence gap — recovery procedure documented in `docs/ITERATIVE_ONBOARDING.md`
8. Fix `create_pipeline` pagination — now uses server-side `?name=` filter instead of fetching all pipelines
9. Remove or warn about `--pat` CLI argument — script now prints a warning when `--pat` appears in `sys.argv`
10. Add `.gitignore` — covers `.venv/`, `__pycache__/`, local tenant directories
11. Update QUICKSTART.md section 5 — now documents how to run `provision_tenant.py`
