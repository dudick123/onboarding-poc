# Tenant Onboarding Automation — Copier POC

A working proof-of-concept for using [Copier](https://copier.readthedocs.io/)
to automate tenant onboarding on the GitOps platform. An operator writes a
YAML request file describing a tenant and its applications; Copier renders it
into a per-app directory tree; a post-generation task creates build repos,
Kustomize config repos, and ArgoCD application repos under `apps/`; and
`provision_tenant.py` drives the Azure DevOps REST API to create those repos,
push content, and register pipelines — only for apps not already live.
Everything with a real-world side effect (`terraform apply`, `docker push`,
`argocd app sync`) still runs in an ADO pipeline gated behind a human
approval. Nothing about that approval model changes — only the manual
copy/rename/edit step in front of it does.

## Start here

| Document | What it's for |
|---|---|
| [`docs/QUICKSTART.md`](docs/QUICKSTART.md) | Run the whole thing yourself in a few commands |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | How the pieces fit together, design decisions, and known gaps |
| [`docs/EXAMPLES.md`](docs/EXAMPLES.md) | Walkthrough of the two example tenants and what differs between them |
| [`docs/PROVISIONING.md`](docs/PROVISIONING.md) | How rendered files become ADO repos, pushes, and pipelines |
| [`docs/ITERATIVE_ONBOARDING.md`](docs/ITERATIVE_ONBOARDING.md) | Onboarding a tenant in phases — adding apps over time |
| [`docs/PRD.md`](docs/PRD.md) | Product requirements and success criteria |

## Repository layout

```
onboarding-template/      The Copier template (would live in ADO as the
                           canonical, version-controlled template repo).
                           Contains copier.yml, provisioning.yaml.jinja,
                           _generate.py.jinja, and exemplar app directories.
onboarding-requests/      Operator input files — what a platform engineer
                           commits to request a tenant, reviewed via PR before
                           any generation occurs.
generated-tenants/        Output of running the template against those request
                           files, included so you can inspect real generated
                           artifacts without running anything.
docs/                     Quickstart, architecture, examples, provisioning,
                           iterative-onboarding, and PRD docs.
provision_tenant.py       Reads provisioning.yaml + a request file, provisions
                           only newly-requested components to ADO.
add_approval_check.py     Wires a manual approval check onto an ADO environment
                           (called by provision_tenant.py, also standalone).
pyproject.toml            Python dependencies (uv). Run `uv sync` to install.
```

## The model, in one paragraph

A platform engineer writes a YAML request file listing the tenant name, sizing
tier, environments, and the applications the tenant needs — each with a name,
type (`angular`, `react`, `springboot`, `go`, `python`, `dotnet`), and
container image path. That file is reviewed via PR. Once approved, `copier copy`
renders `provisioning.yaml` and runs a post-generation task (`_generate.py`)
that creates three discrete ADO repo trees per application under `apps/`:
a build repo (Dockerfile + CI pipeline), a Kustomize config repo (base
manifests + per-environment overlays + promotion pipeline), and an ArgoCD
application repo (Application CRD + sync pipeline). An optional App Gateway
Terraform component is also generated when `include_app_gateway: true`.
`provision_tenant.py` then reads `provisioning.yaml` and drives the ADO REST
API to create repos, push content, and register pipelines, skipping any
component already recorded in `provisioned_components` in the request file.

## Status

This is a proof-of-concept, not a finished tool. The template rendering,
`copier update` flow, and phased provisioning mechanism have all been exercised
against real generated output. The ADO provisioning logic has been tested
against mocked ADO clients; it has not yet been run against a live ADO
organisation (see `docs/PROVISIONING.md` for what to verify before a first
real run).

What's not yet automated: branch policy configuration, ADO service connection
creation, ArgoCD environment approval check wiring (operator configures in ADO
portal post-provisioning), and `kubectl apply` of ArgoCD Application CRDs
(handled by the argocd-sync pipeline after human approval).
