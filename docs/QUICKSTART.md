# Quickstart

Reproduce everything in this package on your own machine in about five
minutes.

## Prerequisites

Install dependencies with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

This installs all dependencies (including Copier) into a project-managed virtual environment. Tested against Copier 9.15.2. Any 9.x release should behave the same way.

## 1. Make the template a Git repo

Copier needs the template to be a Git repository to track versions for
later `copier update` calls. (In real usage this would be an ADO Git repo;
locally, a plain `git init` is enough to try things out.)

```bash
cd onboarding-template
git init
git add -A
git commit -m "initial onboarding template"
cd ..
```

## 2. Generate a tenant from a committed request file

This repo includes two example request files under `onboarding-requests/`.
Generate the full-featured tenant:

```bash
uv run copier copy onboarding-template tenant-acme \
  --data-file onboarding-requests/tenant-acme-input.yaml \
  --defaults
```

You'll get an interactive confirmation for each answer pulled from the
file (press Enter to accept each). Add `--quiet` to skip the prompts
entirely once you trust the file's contents — that's the mode a CI
pipeline or wrapper script would use.

Inspect what got created:

```bash
find tenant-acme -type f
cat tenant-acme/provisioning.yaml
```

## 3. Generate a tenant that opts out of a component

```bash
uv run copier copy onboarding-template tenant-internalbatch \
  --data-file onboarding-requests/tenant-internalbatch-input.yaml \
  --defaults --quiet
```

Compare the file list against tenant-acme — `app-gateway/` and the
`staging` overlay are both absent, because the request file set
`include_app_gateway: false` and only listed `dev`/`prod` under
`environments`.

```bash
find tenant-internalbatch -type f
```

## 4. Try the update flow

Make a platform-wide change to the template — for example, add a new line
to `onboarding-template/config-repo/{{tenant_slug}}/base/deployment.yaml.jinja`
— commit it, then from inside `tenant-acme/`:

```bash
git init && git add -A && git commit -m "tenant repo initial state"
uv run copier update --defaults
```

Copier will pull in the template change as a diff against the tenant's
current files, rather than overwriting everything. If you'd hand-edited
anything in the tenant repo first, that edit survives the update.

## 5. (Not included yet) Push to Azure DevOps

`provisioning.yaml` is the input to this step, but the script that reads it
and drives the ADO REST API isn't built yet in this POC — see
`docs/ARCHITECTURE.md` for the intended design. For now, the repo
creation, push, and pipeline registration described there would be done
manually following the `push_order` and `components` map in
`provisioning.yaml`.

## Common gotchas

- **Reference the template by its real Git URL**, not a relative path, once
  you're doing this for real. `copier update` re-resolves whatever path was
  recorded at generation time in `.copier-answers.yml`; a relative path
  that worked once may not resolve later or from a different machine.
- **`--data-file` values are typed according to `copier.yml`'s question
  definitions** — a YAML list under `environments:` in the request file is
  parsed correctly as a list, no special quoting needed (unlike the
  `--data` CLI flag, which needs `environments='["dev","staging"]'`
  inline-list syntax).
- **Excluding a file's contents with `{% if %}` is not the same as
  excluding the file.** Wrapping content in a conditional just produces an
  empty file. To make a file or directory not exist at all when a
  component is skipped, use `_exclude` in `copier.yml` with a templated
  entry, as done for `app-gateway`, `build-repo`, `config-repo`, and
  `argocd-app` in this template.
