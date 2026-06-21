---
name: add-pipeline-gate
description: Add or review ADO environment approval gates in the promotion pipeline templates.
---

Review and improve the approval gate configuration in the pipeline promotion templates.

## Steps

1. Read `stages/promote.yml` and `stages/argocd-sync.yml` to understand the current gate model
2. Verify the deployment job structure for gated environments:
   - `deployment:` job type (not `job:`) is required for ADO environment gates to apply
   - `environment:` must reference the correct ADO environment name pattern
   - `strategy: runOnce: deploy:` wraps the steps
3. Identify any missing gate patterns:
   - Business hours gate (can be added as an ADO environment check, not in pipeline YAML)
   - Required reviewer count per environment tier (DEV: 0, NONPROD: 1, PROD: 2)
   - Timeout configuration (default ADO gate timeout is 30 days — flag if not explicitly set)
4. Check that the first environment stage does NOT use a deployment job (no gate, auto-sync path)
5. Review the `dependsOn:` chain to confirm sequential promotion order is enforced
6. Suggest any missing checks:
   - Branch policy on the config repo (require PR, squash merge, linked work item)
   - Pipeline run validation (config pipeline must pass before ArgoCD sync stage runs)

## Output

Show any diffs required to `stages/promote.yml` or `stages/argocd-sync.yml`. Separately list the ADO UI/API steps an operator must perform to wire up the approval checks — these cannot be done in pipeline YAML alone.
