# CI Build Pipeline — Examples

Common changes developers make to the build pipeline and Dockerfile.

---

## Change the runtime version

Each pipeline has a language-version variable at the top of `azure-pipelines.yml`:

```yaml
variables:
  CONTAINER_IMAGE: 'myacr.azurecr.io/myorg/myapp'
  GO_VERSION: '1.22'          # or NODE_VERSION, JAVA_VERSION, PYTHON_VERSION, DOTNET_VERSION
```

Update the variable value and update the `FROM` line in `Dockerfile` to match. Both must be changed together — a mismatch between the test agent version and the Dockerfile base image version is a common source of subtle bugs.

---

## Add a pipeline variable

Add to the `variables:` block in `azure-pipelines.yml`:

```yaml
variables:
  CONTAINER_IMAGE: 'myacr.azurecr.io/myorg/myapp'
  GO_VERSION: '1.22'
  MY_FEATURE_FLAG: 'enabled'   # ← add here
```

Reference it in a script step as `$(MY_FEATURE_FLAG)`.

For sensitive values (tokens, passwords), add them in **Pipeline → Edit → Variables** with the lock icon enabled, or store them in an Azure Key Vault-backed variable group. Do not commit secrets to the pipeline YAML.

---

## Change the Dockerfile base image

The build stage image and runtime stage image are set independently in the `Dockerfile`.

To upgrade the runtime image to a newer minor version:

```dockerfile
# Before
FROM alpine:3.19

# After
FROM alpine:3.21
```

Always pin to a specific tag (never `latest`) to ensure reproducible builds. After changing, test locally:

```bash
docker build -t test-image .
docker run --rm -p 8080:8080 test-image
```

---

## Add a layer to the Dockerfile

To install an additional package in the runtime stage:

```dockerfile
FROM alpine:3.19
RUN apk add --no-cache curl      # ← add before COPY
WORKDIR /app
COPY --from=build /build/app .
```

Place package installation before `COPY` instructions so Docker can cache the layer independently of source code changes.

---

## Add an additional trigger branch

By default only `main` triggers a build. To also trigger on `release/*` branches:

```yaml
trigger:
  branches:
    include:
      - main
      - release/*
```

Builds on non-`main` branches will run Test + Build but the resulting image tag will be a non-`main` build ID. The config-repo pipeline trigger only fires on `main` — non-`main` builds do not promote.

---

## Add a PR validation trigger

To run tests on every pull request (without pushing an image):

```yaml
pr:
  branches:
    include:
      - main
```

The `Build` stage references `$(Build.BuildId)` for the image tag. On PR builds, `$(Build.Reason)` is `PullRequest` — you can guard the push step with a condition if needed. The platform template currently does not guard on this; raise with the platform team if PR builds should not push images.

---

## Skip tests in an emergency

Add a pipeline run parameter and guard the Test stage:

```yaml
parameters:
  - name: skipTests
    type: boolean
    default: false

stages:
  - stage: Test
    condition: ${{ eq(parameters.skipTests, false) }}
    ...
```

Queue the pipeline manually and set `skipTests` to `true`. Use sparingly — skipping tests removes the gate that prevents the Build stage from running.

---

## Change the Docker build context or Dockerfile path

By default the build template uses `Dockerfile` at the repo root with `.` as the build context. To override:

```yaml
  - template: stages/build.yml@pipelineTemplates
    parameters:
      containerImage: $(CONTAINER_IMAGE)
      dependsOn: [Test]
      dockerfile: docker/Dockerfile.prod   # ← relative to repo root
      buildContext: src/                   # ← directory passed to docker build
```
