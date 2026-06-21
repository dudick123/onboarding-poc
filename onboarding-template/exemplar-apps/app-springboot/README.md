# {app-name} — Spring Boot Build Repo

Spring Boot 3.3 REST API with Java 21 and Maven. This is the **build repo** in the three-repo GitOps model — it produces the container image that is promoted through environments by the `{app-name}-k8s-manifests` config repo.

## Endpoints

- `GET /` — returns `{"message": "Hello, World!"}`
- `GET /actuator/health` — Spring Boot Actuator health check

## Run locally

```bash
./mvnw spring-boot:run
# → http://localhost:8080
```

No local Maven installation required — the Maven wrapper (`mvnw`) bootstraps Maven 3.9.6 automatically.

## Test locally

```bash
./mvnw test
```

## Build

```bash
./mvnw package -DskipTests
java -jar target/hello-world-0.0.1-SNAPSHOT.jar
```

## Docker

```bash
docker build -t {app-name} .
docker run -p 8080:8080 {app-name}
```

The Dockerfile uses a two-stage build: `eclipse-temurin:21-jdk-alpine` builds the fat JAR; `eclipse-temurin:21-jre-alpine` serves it. The runtime image has no JDK or build tools.

## CI/CD pipeline

The `azure-pipelines.yml` pipeline runs on every push to `main`:

1. **Test** — `mvn test` with JUnit (Surefire) + JaCoCo coverage, published to ADO
2. **Build** — multi-stage Docker build, push to `$(CONTAINER_IMAGE)`, publish `image-meta` artifact

Set `CONTAINER_IMAGE` in **Pipeline → Edit → Variables** before the first run.

## Documentation

| Doc | What it covers |
|-----|----------------|
| [QUICK-START.md](QUICK-START.md) | First-time setup, prerequisites, local development |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Pipeline stages, image-meta artifact, config-repo trigger |
| [EXAMPLES.md](EXAMPLES.md) | Common pipeline and Dockerfile changes |
| [AGENT-SKILLS.md](AGENT-SKILLS.md) | Available Claude Code skills and how to use them |
