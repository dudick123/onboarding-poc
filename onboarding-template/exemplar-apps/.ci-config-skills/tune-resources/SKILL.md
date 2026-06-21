---
name: tune-resources
description: Review and tune CPU/memory requests, limits, HPA, and VPA settings for this application.
---

Analyze and improve the resource configuration for this application's Kubernetes manifests.

## Steps

1. Read `base/deployment.yaml`, `base/hpa.yaml`, and `base/vpa.yaml`
2. Identify the application type (JVM, Node, Go, Python, .NET) from the container image name or build repo
3. Evaluate the current requests/limits against per-type baselines:

   | Runtime | CPU req | Mem req | CPU lim | Mem lim |
   |---------|---------|---------|---------|---------|
   | JVM     | 250m    | 512Mi   | 1       | 1Gi     |
   | Node    | 100m    | 256Mi   | 500m    | 512Mi   |
   | Go      | 50m     | 64Mi    | 500m    | 256Mi   |
   | Python  | 100m    | 128Mi   | 500m    | 512Mi   |
   | .NET    | 200m    | 256Mi   | 1       | 512Mi   |

4. Check HPA:
   - CPU target should be 60–75% for latency-sensitive apps, 70–80% for batch
   - Memory target should be 70–85%
   - `minReplicas` should be ≥ 2 for production workloads
   - `maxReplicas` should provide at least 3× headroom over `minReplicas`

5. Check VPA:
   - `updateMode: Off` is correct for production (recommendation only)
   - `minAllowed` should match or be below current requests
   - `maxAllowed` should match or exceed current limits

6. Identify and flag:
   - Requests equal to limits (prevents VPA from working effectively)
   - Limits more than 4× requests (OOM risk on node)
   - Missing memory limit (unbounded memory is a cluster risk)

## Output

Show recommended changes as diffs to `deployment.yaml`, `hpa.yaml`, and `vpa.yaml`. Explain the reasoning for each change.
