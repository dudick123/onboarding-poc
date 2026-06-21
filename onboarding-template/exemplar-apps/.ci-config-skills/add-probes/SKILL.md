---
name: add-probes
description: Add liveness and readiness probes to the Kubernetes Deployment manifest.
---

Review this config repo and add appropriate liveness and readiness probes to the Deployment.

## Steps

1. Read `base/deployment.yaml` and identify the container port and application type
2. Determine whether a `/health` or `/ready` endpoint exists (check the build repo if accessible, or assume standard conventions per framework)
3. Add both probes to the container spec:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 15
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 10
  failureThreshold: 3
```

4. Adjust `initialDelaySeconds` based on framework startup time:
   - JVM (Spring Boot): liveness 60–90s, readiness 30s
   - Node/Go/Python: liveness 20–30s, readiness 10s
   - .NET: liveness 40–60s, readiness 20s

5. If the app exposes only a single `/health` endpoint, use it for both probes with different thresholds

## Output

Show the exact diff to `base/deployment.yaml` and note any assumptions made about health endpoint paths.
