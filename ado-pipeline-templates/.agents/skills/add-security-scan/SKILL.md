---
name: add-security-scan
description: Add container image and dependency vulnerability scanning steps to the build pipeline templates.
---

Augment the pipeline templates in this repository with security scanning.

## Steps

1. Read `stages/build.yml` and `steps/docker-build-push.yml` to understand the current build flow
2. Add a Trivy container image scan step after the Docker push:
   - Create `steps/trivy-scan.yml`:

```yaml
parameters:
  - name: containerImage
    type: string
  - name: severityThreshold
    type: string
    default: HIGH,CRITICAL
  - name: exitOnVulnerability
    type: boolean
    default: true

steps:
  - script: |
      docker run --rm \
        -v /var/run/docker.sock:/var/run/docker.sock \
        aquasec/trivy:latest image \
          --severity ${{ parameters.severityThreshold }} \
          --exit-code ${{ if parameters.exitOnVulnerability }}1${{ else }}0${{ end }} \
          --format table \
          ${{ parameters.containerImage }}:$(Build.BuildId)
    displayName: Trivy — container image scan
```

3. Add a dependency audit step before the build stage:
   - Create `steps/dependency-audit.yml` with appropriate task per language (npm audit, pip-audit, govulncheck, etc.)

4. Update `stages/build.yml` to compose both new steps:
   - Dependency audit runs before Docker build
   - Trivy scan runs after Docker push, before artifact publish

5. Add parameters to `stages/build.yml`:
   - `runSecurityScan: boolean` (default: true) — allows teams to opt out during initial onboarding
   - `severityThreshold: string` (default: HIGH,CRITICAL)

## Output

Show the new step template files and the diffs to `stages/build.yml`. Note any language-specific audit tool assumptions.
