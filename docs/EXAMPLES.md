# Examples

Two fictitious tenants, generated from the same template, to show how
operator-supplied answers change both which files exist and what's inside them.

## Tenant 1: ACME Industries — multi-app, full platform

Request file: `onboarding-requests/tenant-acme-input.yaml`

```yaml
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
  - name: orders-api
    type: springboot
    container_image: acr.azurecr.io/acme/orders-api
  - name: inventory-api
    type: springboot
    container_image: acr.azurecr.io/acme/inventory-api

key_vault_name: kv-acme-prod
argocd_target_revision: main
include_app_gateway: true
app_gateway_backend_fqdn: acme-internal.svc.cluster.local
app_gateway_hostname: acme.platform.example.com
app_gateway_priority: 100
```

Three apps, `large` tier, three environments, App Gateway enabled. The
post-generation task creates three repo trees per app plus the shared
App Gateway component:

```
generated-tenants/tenant-acme/
├── app-gateway/                   ← shared Terraform (one per tenant)
│   ├── azure-pipelines.yml
│   ├── main.tf
│   └── variables.tf
├── apps/
│   ├── frontend/
│   │   ├── build-repo/            → ADO repo: frontend
│   │   │   ├── Dockerfile
│   │   │   └── azure-pipelines.yml
│   │   ├── config-repo/           → ADO repo: frontend-k8s-manifests
│   │   │   ├── frontend/base/
│   │   │   │   ├── kustomization.yaml
│   │   │   │   ├── deployment.yaml
│   │   │   │   ├── service.yaml
│   │   │   │   └── external-secret.yaml
│   │   │   ├── frontend/overlays/{dev,staging,prod}/
│   │   │   │   ├── kustomization.yaml
│   │   │   │   └── annotation-patch.yaml
│   │   │   └── azure-pipelines.yml
│   │   └── argocd-app/            → ADO repo: frontend-argocd
│   │       ├── {dev,staging,prod}/application.yaml
│   │       └── azure-pipelines.yml
│   ├── orders-api/                ← same structure per app
│   └── inventory-api/             ← same structure per app
└── provisioning.yaml
```

**Tier effect on the rendered Deployment** (`apps/frontend/config-repo/frontend/base/deployment.yaml`):

```yaml
spec:
  replicas: 3
  ...
      containers:
        - name: frontend
          image: acr.azurecr.io/acme/frontend:latest
          resources:
            requests:
              cpu: 500m
              memory: 1Gi
            limits:
              cpu: 1
              memory: 2Gi
```

The `large` tier maps to 3 replicas and the highest resource tier in the
template's tier table — no manual sizing decision needed per tenant.

**The `provisioning.yaml`** maps each generated directory to its ADO destination.
A 3-app tenant with App Gateway produces 10 components:

```yaml
components:
  app_gateway:
    source_dir: app-gateway
    repo_name: acme-app-gateway
    pipeline_name: acme-app-gateway-plan-apply
    environments:
      - name: app-gateway-acme-approval
        requires_approval: true
  frontend_build:
    source_dir: apps/frontend/build-repo
    repo_name: frontend
    pipeline_name: frontend-build-push
    environments: []
  frontend_config:
    source_dir: apps/frontend/config-repo
    repo_name: frontend-k8s-manifests
    pipeline_name: frontend-kustomize-build
    environments: []
  frontend_argocd:
    source_dir: apps/frontend/argocd-app
    repo_name: frontend-argocd
    pipeline_name: frontend-argocd-sync
    environments:
      - name: argocd-sync-acme-frontend-approval
        requires_approval: true
  orders_api_build:   ...   # same pattern for orders-api
  orders_api_config:  ...
  orders_api_argocd:  ...
  inventory_api_build:  ...  # same pattern for inventory-api
  inventory_api_config: ...
  inventory_api_argocd: ...

push_order:
  - app_gateway
  - frontend_build
  - frontend_config
  - frontend_argocd
  - orders_api_build
  - orders_api_config
  - orders_api_argocd
  - inventory_api_build
  - inventory_api_config
  - inventory_api_argocd
```

**The approval-gated environments.** Each argocd-app repo's pipeline and the
App Gateway pipeline include a deployment job targeting an ADO environment with
an approval check:

```yaml
# apps/frontend/argocd-app/azure-pipelines.yml (generated)
stages:
  - template: stages/argocd-sync.yml@pipelineTemplates
    parameters:
      env: staging
      appName: 'frontend'
      tenantSlug: 'acme'
      argocdServer: $(ARGOCD_SERVER_STAGING)
      argocdToken: $(ARGOCD_TOKEN_STAGING)
      dependsOn: [SyncDEV]
```

The `stages/argocd-sync.yml` template creates a `deployment:` job that gates
against an ADO environment (`argocd-sync-{tenant}-{app}-approval`), enforcing
human approval before ArgoCD syncs each non-first environment.

---

## Tenant 2: Internal Batch Processing — single app, no App Gateway

Request file: `onboarding-requests/tenant-internalbatch-input.yaml`

```yaml
tenant_slug: internalbatch
tenant_display_name: "Internal Batch Processing"
ado_project: platform-tenants
ado_org_name: my-org
resource_tier: small
environments:
  - dev
  - prod

apps:
  - name: batch-worker
    type: python
    container_image: acr.azurecr.io/internalbatch/worker

key_vault_name: kv-internalbatch-prod
argocd_target_revision: main
include_app_gateway: false
```

One app (`python` type), `small` tier, two environments (`dev`/`prod` only),
no App Gateway.

```
generated-tenants/tenant-internalbatch/
├── apps/
│   └── batch-worker/
│       ├── build-repo/            → ADO repo: batch-worker
│       ├── config-repo/           → ADO repo: batch-worker-k8s-manifests
│       │   └── batch-worker/overlays/{dev,prod}/   ← no staging overlay
│       └── argocd-app/            → ADO repo: batch-worker-argocd
└── provisioning.yaml
```

Compare what's absent versus ACME:
- No `app-gateway/` directory at all
- No `staging` overlay under `config-repo/` — only `dev` and `prod`
- `provisioning.yaml` has 3 components (`batch_worker_build/config/argocd`),
  not 10

**Tier effect, for comparison against ACME:**

```yaml
spec:
  replicas: 1
  ...
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 250m
              memory: 512Mi
```

The `small` tier produces a noticeably lighter footprint than ACME's `large`
tier, from the same template logic.

**`provisioning.yaml` for internalbatch:**

```yaml
components:
  batch_worker_build:
    source_dir: apps/batch-worker/build-repo
    repo_name: batch-worker
    pipeline_name: batch-worker-build-push
    environments: []
  batch_worker_config:
    source_dir: apps/batch-worker/config-repo
    repo_name: batch-worker-k8s-manifests
    pipeline_name: batch-worker-kustomize-build
    environments: []
  batch_worker_argocd:
    source_dir: apps/batch-worker/argocd-app
    repo_name: batch-worker-argocd
    pipeline_name: batch-worker-argocd-sync
    environments:
      - name: argocd-sync-internalbatch-batch-worker-approval
        requires_approval: true

push_order:
  - batch_worker_build
  - batch_worker_config
  - batch_worker_argocd
```

This is the file `provision_tenant.py` iterates over to create ADO repos,
push content, and register pipelines — see [`ARCHITECTURE.md`](ARCHITECTURE.md)
for how that works end to end.
