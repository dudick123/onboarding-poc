# Quick Start — Spring Boot Build Repo

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Java JDK | 21+ | https://adoptium.net/ |
| Docker | 24+ | https://docs.docker.com/get-docker/ |
| Access to ADO project | — | Provided by platform team |

No local Maven installation is required — the Maven wrapper (`mvnw`) bootstraps Maven 3.9.6 automatically on first use.

---

## Step 1 — Clone and run locally

```bash
git clone https://dev.azure.com/{ado-org}/{ado-project}/_git/{app-name}
cd {app-name}
./mvnw spring-boot:run
```

Open http://localhost:8080 — you should see `{"message":"Hello, World!"}`.
Open http://localhost:8080/actuator/health — you should see `{"status":"UP"}`.

---

## Step 2 — Run tests

```bash
./mvnw test
```

Test results and JaCoCo coverage reports land in `target/surefire-reports/` and `target/site/jacoco/`.

---

## Step 3 — Build the fat JAR

```bash
./mvnw package -DskipTests
java -jar target/hello-world-0.0.1-SNAPSHOT.jar
```

---

## Step 4 — Build and run the Docker image locally

```bash
docker build -t {app-name}:local .
docker run --rm -p 8080:8080 {app-name}:local
```

Note: the first Docker build downloads the Maven wrapper's Maven distribution inside the builder stage. Subsequent builds use the Docker layer cache and are fast.

Test the containerized app:

```bash
curl http://localhost:8080/actuator/health
# {"status":"UP"}
```

---

## Step 5 — Set the CONTAINER_IMAGE pipeline variable

1. In ADO, navigate to **Pipelines → {app-name} → Edit → Variables**
2. Add a variable named `CONTAINER_IMAGE` with value `myacr.azurecr.io/myorg/{app-name}`
3. Do not lock the variable (it is not a secret)

---

## Step 6 — Trigger the first pipeline run

Push a commit to `main` (or queue the pipeline manually in ADO).

Expected run sequence:

1. **Test stage** — `mvn test` runs; JUnit + JaCoCo results appear in the **Tests** and **Code Coverage** tabs
2. **Build stage** — Docker build + push (JVM build inside Docker, no local JDK needed on the agent)
3. **image-meta artifact** — published; visible under **Artifacts** in the run summary

Note: the Docker build inside the pipeline uses the JDK image to run Maven, which downloads dependencies. Subsequent runs use the agent's Docker layer cache if available.

---

## Step 7 — Verify the config-repo trigger

After the build pipeline completes on `main`, check **Pipelines → {app-name}-k8s-manifests** — a new run should queue within ~60 seconds.

---

## Common first issues

| Symptom | Fix |
|---------|-----|
| `./mvnw: Permission denied` | Run `chmod +x mvnw` |
| `JAVA_HOME is not set` | Install JDK 21 and set `JAVA_HOME`; or use `sdk install java 21` (SDKMAN) |
| Slow first `docker build` | Maven downloads dependencies inside the builder stage; subsequent builds use the Docker cache |
| Pipeline test stage fails with no JDK 21 | The pipeline uses `jdkVersionOption: '1.21'`; ensure ADO agent has Java 21 available |
