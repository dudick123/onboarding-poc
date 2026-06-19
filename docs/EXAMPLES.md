# Examples

Two fictitious tenants, generated from the same template, to show how
operator-supplied answers change both which files exist and what's inside
them.

## Tenant 1: ACME Industries — the typical case

Request file: `onboarding-requests/tenant-acme-input.yaml`

```yaml
tenant_slug: acme
tenant_display_name: "ACME Industries"
ado_project: platform-tenants
resource_tier: large
environments:
  - dev
  - staging
  - prod

include_app_gateway: true
include_build_repo: true
include_config_repo: true
include_argocd_app: true

container_image: acr.azurecr.io/acme/orders-api
key_vault_name: kv-acme-prod
app_gateway_backend_fqdn: acme-internal.svc.cluster.local
app_gateway_hostname: acme.platform.example.com
argocd_target_revision: main
```

All four components requested, large tier, all three environments. This
generates 17 files across four component directories plus
`provisioning.yaml`.

**Tier effect on the rendered Deployment**
(`generated-tenants/tenant-acme/config-repo/acme/base/deployment.yaml`):

```yaml
spec:
  replicas: 3
  ...
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

**The approval-gated pipelines.** Both
`app-gateway/azure-pipelines.yml` and `argocd-app/azure-pipelines.yml`
include a stage that depends on an ADO `environment:` with an approval
check, so the actual `terraform apply` or `argocd app sync` only runs after
a human approves:

```yaml
  - stage: Apply
    dependsOn: Plan
    jobs:
      - deployment: TerraformApply
        environment: 'app-gateway-acme-approval'
        strategy:
          runOnce:
            deploy:
              steps:
                - script: terraform apply tfplan
```

## Tenant 2: Internal Batch Processing — opting out of a component

Request file: `onboarding-requests/tenant-internalbatch-input.yaml`

```yaml
tenant_slug: internalbatch
tenant_display_name: "Internal Batch Processing"
ado_project: platform-tenants
resource_tier: small
environments:
  - dev
  - prod

include_app_gateway: false
include_build_repo: true
include_config_repo: true
include_argocd_app: true

container_image: acr.azurecr.io/internalbatch/worker
key_vault_name: kv-internalbatch-prod
argocd_target_revision: main
```

This tenant has no inbound HTTP traffic to route (an internal batch job),
so the operator set `include_app_gateway: false`. It also only deploys to
`dev` and `prod`, no `staging`.

**Result: 12 files, not 17.** `app-gateway/` does not exist anywhere in the
output — not as an empty directory, not as files with blank content. The
`staging` overlay under `config-repo/` is likewise entirely absent. Compare
the file listings:

```
generated-tenants/tenant-acme/           generated-tenants/tenant-internalbatch/
├── app-gateway/              ←missing→
├── argocd-app/                ├── argocd-app/
├── build-repo/                 ├── build-repo/
├── config-repo/                 ├── config-repo/
│   └── overlays/                  │   └── overlays/
│       ├── dev/                       │       ├── dev/
│       ├── staging/         ←missing→
│       └── prod/                       │       └── prod/
└── provisioning.yaml                  └── provisioning.yaml
```

**Tier effect, for comparison against ACME**
(`generated-tenants/tenant-internalbatch/config-repo/internalbatch/base/deployment.yaml`):

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

The `small` tier produces a noticeably lighter footprint than ACME's
`large` tier, from the same template logic.

## The `provisioning.yaml` difference

ACME's `provisioning.yaml` lists four entries under `components` and four
under `push_order`. Internal Batch's lists three of each — `app_gateway`
is absent from both, consistent with the file-tree difference above:

```yaml
# ACME
push_order:
  - build_repo
  - config_repo
  - app_gateway
  - argocd_app

# Internal Batch
push_order:
  - build_repo
  - config_repo
  - argocd_app
```

This is the file a provisioning script would iterate over to create ADO
repos, push content, and register pipelines — see
[`ARCHITECTURE.md`](ARCHITECTURE.md) for how that's intended to work.
