---
name: add-network-policy
description: Add a Kubernetes NetworkPolicy to restrict ingress and egress for this application.
---

Add a least-privilege NetworkPolicy to this config repo.

## Steps

1. Read `base/kustomization.yaml` to understand the app name, namespace labels, and existing resources
2. Identify what traffic this app legitimately needs:
   - Inbound: from ingress controller, from other apps in the same namespace
   - Outbound: to databases, external APIs, DNS (port 53)
3. Create `base/network-policy.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {app-name}
  namespace: {tenant-slug}
spec:
  podSelector:
    matchLabels:
      app: {app-name}
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
      ports:
        - port: 8080
  egress:
    - ports:
        - port: 53
          protocol: UDP
    # Add additional egress rules as needed
```

4. Add `network-policy.yaml` to `resources:` in `base/kustomization.yaml`
5. Note any egress rules that need to be added based on the application's known dependencies

## Output

Show the new `network-policy.yaml` and the diff to `kustomization.yaml`. Flag any traffic patterns that require operator input to complete.
