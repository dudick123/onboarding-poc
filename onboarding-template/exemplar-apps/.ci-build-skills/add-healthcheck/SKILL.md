---
name: add-healthcheck
description: Add an appropriate HEALTHCHECK instruction to the Dockerfile and, if needed, a /health endpoint to the application.
---

Review this repository and add a proper Docker HEALTHCHECK.

## Steps

1. Read the Dockerfile and identify the runtime stage and exposed port
2. Read the source code to determine whether a `/health` endpoint already exists
3. If no health endpoint exists, add one:
   - It should return HTTP 200 with a simple JSON body (e.g., `{"status":"ok"}`)
   - It must NOT require authentication
   - It should verify the application is genuinely ready to serve traffic (not just that the process is alive)
4. Choose the right probe mechanism for the runtime image:
   - If `curl` is available: `curl -f http://localhost:{PORT}/health`
   - If `wget` is available: `wget -qO- http://localhost:{PORT}/health`
   - If neither is available: install one in the runtime stage, or use a TCP check
5. Add the `HEALTHCHECK` instruction to the **runtime stage** of the Dockerfile:
   ```
   HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
     CMD curl -f http://localhost:{PORT}/health || exit 1
   ```
6. Adjust `--start-period` based on the application type:
   - JVM (Spring Boot): 60–90s
   - Node/Go/Python: 20–40s
   - .NET: 30–60s

## Output

Show the exact Dockerfile change and any source code changes needed for the health endpoint.
