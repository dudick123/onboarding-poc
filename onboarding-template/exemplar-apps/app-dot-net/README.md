# {app-name} — .NET Build Repo

Minimal ASP.NET Core 8 Web API using Minimal APIs. This is the **build repo** in the three-repo GitOps model — it produces the container image that is promoted through environments by the `{app-name}-k8s-manifests` config repo.

## Endpoints

- `GET /` — returns `{"message": "Hello, World!"}`
- `GET /health` — returns `{"status": "ok"}`

## Run locally

```bash
dotnet run
# → http://localhost:8080
```

## Test locally

```bash
dotnet test tests/
```

## Publish

```bash
dotnet publish -c Release -o ./publish
dotnet ./publish/app.dll
```

## Docker

```bash
docker build -t {app-name} .
docker run -p 8080:8080 {app-name}
```

The Dockerfile uses a two-stage build: `mcr.microsoft.com/dotnet/sdk:8.0` builds and publishes the app; `mcr.microsoft.com/dotnet/aspnet:8.0` serves it. The runtime image has no .NET SDK or build tools.

The `AssemblyName` in `HelloWorld.csproj` is set to `app` to match the Dockerfile's `ENTRYPOINT ["dotnet", "app.dll"]`.

## CI/CD pipeline

The `azure-pipelines.yml` pipeline runs on every push to `main`:

1. **Test** — `dotnet test` with Coverlet coverage, VSTest + Cobertura output published to ADO
2. **Build** — multi-stage Docker build, push to `$(CONTAINER_IMAGE)`, publish `image-meta` artifact

Set `CONTAINER_IMAGE` in **Pipeline → Edit → Variables** before the first run.

## Documentation

| Doc | What it covers |
|-----|----------------|
| [QUICK-START.md](QUICK-START.md) | First-time setup, prerequisites, local development |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Pipeline stages, image-meta artifact, config-repo trigger |
| [EXAMPLES.md](EXAMPLES.md) | Common pipeline and Dockerfile changes |
| [AGENT-SKILLS.md](AGENT-SKILLS.md) | Available Claude Code skills and how to use them |
