# CI Build Pipeline — Architecture

This repository is the **build repo** in a three-repo GitOps model. Its sole responsibility is to produce a tested, tagged container image and publish an artifact that triggers the downstream configuration pipeline.

## Three-repo model

| Repo | ADO repo name | Role |
|------|--------------|------|
| **This repo** | `{app-name}` | Test + build container image |
| Config repo | `{app-name}-k8s-manifests` | Update Kustomize manifests, promote across environments |
| ArgoCD repo | `{app-name}-argocd` | ArgoCD Application CRDs, sync pipeline |

A merge to `main` in this repo is the starting pistol for the entire promotion chain. No manual handoff is required.

## Pipeline stages

```
[Test]  ──►  [Build]
```

### Test stage

Defined inline in `azure-pipelines.yml`. Runs unit tests using the language-native test framework, then publishes:
- JUnit XML results → ADO Tests tab
- Cobertura XML coverage → ADO Coverage tab

The Build stage has `dependsOn: [Test]` — a test failure prevents image push.

### Build stage (platform template)

Sourced from `stages/build.yml@pipelineTemplates` in the `platform-pipeline-templates` ADO repository. It runs three steps in sequence:

**1. Docker build + push (`steps/docker-build-push.yml`)**

```
docker build -f Dockerfile \
  -t $(CONTAINER_IMAGE):$(Build.BuildId) \
  -t $(CONTAINER_IMAGE):latest \
  .
docker push $(CONTAINER_IMAGE):$(Build.BuildId)
docker push $(CONTAINER_IMAGE):latest
```

The `$(Build.BuildId)` tag is immutable — it uniquely identifies which pipeline run produced the image.

**2. Image metadata capture (`steps/capture-and-publish-image-meta.yml`)**

Inspects the pushed image to get the registry digest, then writes `image-meta.json`:

```json
{
  "containerImage": "myacr.azurecr.io/myapp",
  "imageTag": "123",
  "imageSha": "sha256:abc123...",
  "buildId": "123",
  "buildUrl": "https://dev.azure.com/org/project/_build/results?buildId=123",
  "gitCommit": "a1b2c3d4...",
  "builtAt": "2024-01-15T10:30:00Z"
}
```

**3. Artifact publish**

`image-meta.json` is published as a pipeline artifact named `image-meta`. The config-repo pipeline downloads this artifact to know which image tag and SHA to promote.

## Config-repo auto-trigger

The `{app-name}-k8s-manifests` config pipeline declares this pipeline as an [ADO pipeline resource](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/resources?view=azure-devops&tabs=schema#resources-pipelines):

```yaml
resources:
  pipelines:
    - pipeline: BuildPipeline
      source: {app-name}
      trigger:
        branches:
          include:
            - main
```

When a build completes on `main`, ADO automatically queues the config pipeline. The config pipeline then:
1. Downloads the `image-meta` artifact from this run
2. Updates the Kustomize overlay image tag
3. Opens a PR against the config repo
4. Gates behind an ADO environment approval for non-first environments
5. Calls ArgoCD sync after approval

## Dockerfile structure

All Dockerfiles in this exemplar use multi-stage builds:

```
Stage 1 (build)   — full compiler/toolchain image → produces binary/artifact
Stage 2 (runtime) — minimal image → copies only the built artifact
```

**Why this matters:**
- Build tools, source code, and intermediate files are never in the deployed image
- Runtime image surface area is minimal (smaller attack surface)
- Image size is significantly smaller than a single-stage build

Do not add build tools, compilers, or package managers to the runtime stage.

## Key variable: CONTAINER_IMAGE

The `CONTAINER_IMAGE` pipeline variable controls where the built image is pushed. It must be set to the full registry path (without tag), e.g. `myacr.azurecr.io/myorg/myapp`.

Set it in: **Pipeline → Edit → Variables** or add it to a variable group referenced in the pipeline.

The default placeholder in `azure-pipelines.yml` (`REPLACE_WITH_YOUR_REGISTRY_AND_IMAGE`) intentionally fails fast — the build stage will error rather than silently push to an unintended location.

## Platform template repository

The `resources.repositories` block in `azure-pipelines.yml` declares a dependency on `platform-pipeline-templates`:

```yaml
resources:
  repositories:
    - repository: pipelineTemplates
      type: git
      name: platform-pipeline-templates
      ref: main
```

Stage and step templates are referenced as `template: stages/build.yml@pipelineTemplates`. The platform team owns the templates; updates to them flow to all tenants automatically.
