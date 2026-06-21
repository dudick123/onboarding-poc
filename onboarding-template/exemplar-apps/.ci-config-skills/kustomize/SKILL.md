---
name: kustomize
description: Understand, extend, and troubleshoot the Kustomize base/overlay structure used by this config repo.
---

This repo uses a Kustomize base/overlay layout managed by an ADO promotion pipeline. Understand the conventions before making changes.

## Repo layout

```
{app-name}/
  base/
    kustomization.yaml      # commonLabels, resource list
    deployment.yaml
    serviceaccount.yaml
    service.yaml
    hpa.yaml                # autoscaling/v2
    vpa.yaml                # updateMode: Off (recommendation only)
    pdb.yaml
    external-secret.yaml
  overlays/
    {env}/
      kustomization.yaml    # namespace, namePrefix, replicas, images, patches
      annotation-patch.yaml # pipeline-owned — do not edit by hand
```

## Key conventions

**`namePrefix: {env}-`** — every resource name gains the env prefix at render time. Reference resources by their base name in patches; Kustomize applies the prefix automatically.

**`images:` block** — the `newTag` field is overwritten on every pipeline run via `kustomize edit set image`. Never set it to a real tag by hand; use `pending` as the stable placeholder.

**`annotation-patch.yaml`** — owned entirely by the promotion pipeline. It carries `platform.io/image-sha`, `platform.io/image-tag`, `platform.io/promoted-at`, and `platform.io/source-pipeline`. Editing it by hand will be overwritten on the next pipeline run.

**`commonLabels` in base** — applied to all resources. Do not add the same label keys in individual resource files or patches; they will conflict.

**`namespace` in overlays** — the overlay sets `namespace: {tenant}-{env}`. Resources in base use the tenant namespace (no env suffix); the overlay overrides it. Avoid hardcoding namespaces in base files.

## Validating a change

Always validate all overlays after any edit to base:

```bash
for env in dev nonprod prod; do
  echo "=== $env ===" && kustomize build {app-name}/overlays/$env
done
```

## Adding a new resource to base

1. Create the manifest file in `{app-name}/base/`
2. Add it to `resources:` in `{app-name}/base/kustomization.yaml`
3. Run the validation command above — confirm the resource appears in all overlay outputs with the correct `namePrefix` and `namespace`

## Adding an overlay-specific patch

Create a strategic merge patch file in the overlay directory and reference it under `patches:`:

```yaml
# overlays/prod/replica-patch.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {app-name}   # base name — namePrefix is applied by Kustomize
spec:
  replicas: 3
```

```yaml
# overlays/prod/kustomization.yaml  (add to existing patches list)
patches:
  - path: annotation-patch.yaml
  - path: replica-patch.yaml
```

Do not add env-specific replica counts this way if the overlay `kustomization.yaml` already has a `replicas:` block — use that instead.

## Adding per-env environment variables

Add a ConfigMap generator or a patch against the Deployment's `env:` / `envFrom:` block. Prefer `envFrom` + ExternalSecret for secrets (already wired via `{tenant}-secrets`). For non-secret config, use a per-overlay patch:

```yaml
# overlays/dev/env-patch.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {app-name}
spec:
  template:
    spec:
      containers:
        - name: {app-name}
          env:
            - name: LOG_LEVEL
              value: debug
```

## What the pipeline does on each run

1. Downloads `image-meta.json` artifact from the triggering build pipeline
2. Runs `kustomize edit set image {containerImage}:{imageTag}` in the overlay directory
3. Overwrites `annotation-patch.yaml` with current SHA, tag, timestamp, and build URL via `printf`
4. Runs `kustomize build overlays/{env}` to validate
5. Commits the overlay changes to a branch and opens a PR
6. For non-first environments: waits for ADO environment approval, then calls ArgoCD sync

## Common issues

| Symptom | Likely cause |
|---------|--------------|
| `kustomize build` fails after adding a resource | File not listed in `base/kustomization.yaml` |
| Resource appears in wrong namespace | Namespace hardcoded in base manifest; remove it and let the overlay set it |
| `namePrefix` applied twice | Resource name in a patch already includes the env prefix |
| Annotation patch conflicts | Another patch targets the same `metadata.annotations` keys as `annotation-patch.yaml` |
| Image tag reverts to `pending` after merge | Pipeline ran `kustomize edit set image` after your manual tag change — expected behavior |
