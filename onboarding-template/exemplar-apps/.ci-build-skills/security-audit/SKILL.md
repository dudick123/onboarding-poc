---
name: security-audit
description: Audit this repository for security issues in the Dockerfile, dependencies, and source code.
---

Review this repository for security weaknesses and produce a prioritized finding list.

## Checks

### Dockerfile
- Runtime stage runs as a non-root USER
- No secrets or credentials embedded in ENV or ARG instructions
- Build tools absent from the runtime stage
- Base image tag is pinned (not `latest`)
- No `COPY . .` in the runtime stage (use explicit paths or .dockerignore)
- `.dockerignore` excludes `.git`, `node_modules`, test directories, and local env files

### Dependencies
- No dependency pinned to a broad range that allows major-version drift
- No packages with known CVEs (flag any that appear abandoned or unmaintained)
- Dev-only dependencies not bundled into production builds

### Source code patterns
- No credentials, API keys, or tokens hardcoded in source files
- User-controlled input is not passed directly to shell commands
- SQL queries use parameterized statements, not string concatenation
- TLS verification is not disabled (e.g., `verify=False`, `InsecureSkipVerify`)
- Deserialization of untrusted data is not performed without schema validation

## Output

For each finding:
```
[SEVERITY] <file>:<line>  —  <short description>
Detail: <what the risk is>
Fix:    <concrete remediation>
```

Severity levels: **CRITICAL** | **HIGH** | **MEDIUM** | **LOW**

Summarize at the end with total counts per severity and the single highest-priority fix to apply first.
