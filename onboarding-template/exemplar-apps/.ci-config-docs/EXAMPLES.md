# CI Config Repo — Examples

Concrete examples for common manifest changes. Always validate after editing:

```bash
kustomize build {app-name}/overlays/dev
```

---

## Change replica counts per environment

Replica counts are set in each overlay's `kustomization.yaml` under the `replicas:` block — not in `base/deployment.yaml`.

```yaml
# overlays/prod/kustomization.yaml
replicas:
  - name: {app-name}
    count: 3         # ← change this value
```

The `base/deployment.yaml` `spec.replicas` value sets the default used by any overlay that does not declare a `replicas:` block.

---

## Add a non-secret environment variable

For configuration that is not sensitive, add a strategic merge patch in the overlay:

```yaml
# overlays/dev/env-patch.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {app-name}       # base name — namePrefix is applied by Kustomize
spec:
  template:
    spec:
      containers:
        - name: {app-name}
          env:
            - name: LOG_LEVEL
              value: debug
```

Register the patch in the overlay `kustomization.yaml`:

```yaml
# overlays/dev/kustomization.yaml
patches:
  - path: annotation-patch.yaml
  - path: env-patch.yaml          # ← add this
```

For prod, use `value: warn` in `overlays/prod/env-patch.yaml`.

---

## Add a secret environment variable

Secrets are managed via ExternalSecret and Azure Key Vault. The existing `external-secret.yaml` extracts all secrets for this tenant under the `{tenant}` Key Vault secret name as a Kubernetes Secret named `{tenant}-secrets`.

The Deployment already pulls all of those as environment variables via:

```yaml
envFrom:
  - secretRef:
      name: {tenant}-secrets
```

To add a new secret: add the key to the Key Vault secret (JSON object) under the tenant's key. The ExternalSecret refresh interval is 1 hour, or trigger a manual sync:

```bash
kubectl annotate externalsecret {tenant}-secrets \
  force-sync=$(date +%s) -n {tenant}-{env} --overwrite
```

---

## Add a new Kubernetes resource

1. Create the manifest file in `{app-name}/base/`:

```yaml
# {app-name}/base/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {app-name}-config
  namespace: {tenant}
data:
  APP_MODE: production
```

2. Register it in `{app-name}/base/kustomization.yaml`:

```yaml
resources:
  - serviceaccount.yaml
  - deployment.yaml
  - service.yaml
  - hpa.yaml
  - vpa.yaml
  - pdb.yaml
  - external-secret.yaml
  - configmap.yaml      # ← add here
```

3. Validate all overlays:

```bash
for env in dev staging prod; do
  kustomize build {app-name}/overlays/$env | grep -A5 "kind: ConfigMap"
done
```

Confirm the ConfigMap appears in each overlay output with the correct `namespace` and `namePrefix` applied.

---

## Add a label to all resources

`commonLabels` in `base/kustomization.yaml` applies labels to every resource:

```yaml
commonLabels:
  app.kubernetes.io/part-of: {tenant}
  app.kubernetes.io/name: {app-name}
  platform.io/tenant: {tenant}
  platform.io/tier: medium
  my-team/cost-center: eng-123    # ← new label
```

Labels in `commonLabels` are also applied to `selector.matchLabels` on Deployments. If the Deployment already exists in the cluster, changing `commonLabels` creates a selector conflict — this is a destructive change that requires deleting and re-creating the Deployment. For annotation-only changes, use a patch instead.

---

## Add a resource-only annotation (non-selector)

To add an annotation without touching selectors:

```yaml
# {app-name}/base/annotations-patch.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {app-name}
  annotations:
    my-team/runbook: "https://wiki.example.com/runbook/{app-name}"
```

Add to `base/kustomization.yaml`:

```yaml
patches:
  - path: annotations-patch.yaml
```

---

## Change the service port

If the application listens on a port other than 8080:

```yaml
# overlays/dev/port-patch.yaml  (or in base if all environments change)
apiVersion: v1
kind: Service
metadata:
  name: {app-name}
spec:
  ports:
    - port: 9090
      targetPort: 9090
```

Also update the Deployment's container port in `base/deployment.yaml` if it is declared explicitly (the starter template does not declare a `containerPort`, so only the Service needs updating).

---

## Override HPA thresholds for production

```yaml
# overlays/prod/hpa-patch.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {app-name}
spec:
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60    # tighter threshold for prod
```

Add to `overlays/prod/kustomization.yaml`:

```yaml
patches:
  - path: annotation-patch.yaml
  - path: hpa-patch.yaml
```

---

## Roll back to a previous image

The pipeline owns the image tag in `overlays/{env}/kustomization.yaml`. To roll back:

1. Check the ADO build history for the build ID you want to revert to
2. Manually edit `overlays/{env}/kustomization.yaml`:

```yaml
images:
  - name: {container-image}
    newTag: "411"    # ← previous build ID
```

3. Update `overlays/{env}/annotation-patch.yaml` annotations to reflect the rollback
4. Open a PR and merge — ArgoCD syncs the rolled-back image

Alternatively, use the `{app-name}-argocd` repo's sync pipeline to trigger an ArgoCD sync against a specific Git revision of this repo.
