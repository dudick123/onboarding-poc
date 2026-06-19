# Tenant Onboarding Automation — Copier POC

A working proof-of-concept for using [Copier](https://copier.readthedocs.io/)
to automate the file-generation half of tenant onboarding on the GitOps
platform: Application Gateway Terraform, the container build repo, the
Kustomize config repo, and the ArgoCD Application + sync pipeline. Copier
renders correct, consistent files from a single tenant request; everything
with a real-world side effect (`terraform apply`, `docker push`,
`argocd app sync`) still runs in an Azure DevOps pipeline gated behind a
human approval, exactly as it does today. Nothing about that approval model
changes — only the manual copy/rename/edit step in front of it does.

## Start here

| Document | What it's for |
|---|---|
| [`docs/QUICKSTART.md`](docs/QUICKSTART.md) | Run the whole thing yourself in a few commands |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | How the pieces fit together, design decisions, and known gaps |
| [`docs/EXAMPLES.md`](docs/EXAMPLES.md) | Walkthrough of the two example tenants and what differs between them |
| [`docs/PROVISIONING.md`](docs/PROVISIONING.md) | How rendered files become ADO repos, pushes, and pipelines |
| [`docs/ITERATIVE_ONBOARDING.md`](docs/ITERATIVE_ONBOARDING.md) | Onboarding a tenant in phases across multiple PRs over time |

## Repository layout

```
onboarding-template/      The Copier template (would live in ADO as the
                           canonical, version-controlled template repo)
onboarding-requests/      Example operator input files — what a platform
                           engineer commits to request a tenant, including
                           a full 3-phase request history for ACME
generated-tenants/        Output of running the template against those
                           request files, included so you can inspect
                           real generated artifacts without running anything
docs/                      Quickstart, architecture, examples, provisioning,
                           and iterative-onboarding docs
provision_tenant.py        Reads provisioning.yaml + a request file, pushes
                           only newly-requested components to ADO
add_approval_check.py      Wires a manual approval check onto an ADO
                           environment (called by provision_tenant.py)
requirements.txt           Python dependencies for the two scripts above
```

## The model, in one paragraph

A platform engineer (or eventually a self-service requester) writes a YAML
request file describing a tenant — name, sizing tier, which of the four
components it needs, and component-specific details like an App Gateway
hostname. That file gets reviewed via PR like any other change. Once
approved, `copier copy` renders the four component directories (skipping
whichever ones the request opted out of) plus a `provisioning.yaml` file
that maps each rendered component to its destination ADO repo name,
pipeline name, and any required approval-gated environments. A second
script (`provision_tenant.py`, included and tested via mocked ADO clients —
see `docs/PROVISIONING.md`) reads
`provisioning.yaml` and drives the ADO REST API to create repos, push the
rendered content, and register pipelines — in the dependency order
`provisioning.yaml` specifies. The actual `terraform apply`, `docker push`,
and `argocd app sync` stay exactly where they are: ADO pipeline stages
behind an approval check.

## Status

This is a proof-of-concept, not a finished tool, but it now covers the full
loop: Copier renders the files, `provision_tenant.py` pushes them to ADO,
and the phased-onboarding mechanism (`provisioned_components`) lets that
happen incrementally across multiple PRs over time. All of this has been
exercised — the template rendering and `copier update` flow against real
output, and the ADO provisioning logic against mocked ADO clients (no live
ADO org was used in building this package; see `docs/PROVISIONING.md` for
what to verify before a first real run).

What's genuinely not done yet: branch policy automation, service connection
creation, and the ArgoCD Application's actual `kubectl apply` / cluster-side
registration (the rendered `application.yaml` is pushed to a repo; applying
it to the cluster is the `argocd-sync` pipeline's job, gated behind human
approval, same as today).
