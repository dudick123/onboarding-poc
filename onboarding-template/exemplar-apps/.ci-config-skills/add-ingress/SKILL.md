---
name: add-ingress
description: Add a Kubernetes Ingress resource to expose this application externally.
---

Add an Ingress resource to this config repo to expose the application via the ingress controller.

## Steps

1. Read `base/service.yaml` to confirm the service name and port
2. Read `base/kustomization.yaml` to get the app name and tenant context
3. Create `base/ingress.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {app-name}
  namespace: {tenant-slug}
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    # Add TLS, rate-limit, or auth annotations as needed
spec:
  ingressClassName: nginx
  rules:
    - host: {app-name}.{tenant-slug}.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: {app-name}
                port:
                  number: 8080
  tls:
    - hosts:
        - {app-name}.{tenant-slug}.example.com
      secretName: {app-name}-tls
```

4. Add `ingress.yaml` to `resources:` in `base/kustomization.yaml`
5. Add a hostname patch to each overlay's `kustomization.yaml` so the hostname is environment-specific:
   - dev: `{app-name}.{tenant}-dev.example.com`
   - nonprod: `{app-name}.{tenant}-nonprod.example.com`
   - prod: `{app-name}.{tenant}.example.com`

## Output

Show the new `ingress.yaml`, the patch structure for overlays, and the diffs to affected `kustomization.yaml` files. Note any TLS certificate provisioning assumptions.
