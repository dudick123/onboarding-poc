---
name: upgrade-dependencies
description: Upgrade all dependencies in this repository to their latest stable versions and summarize breaking changes.
---

Perform a dependency upgrade for this build repository.

## Steps

1. Identify the dependency manifest(s) in use:
   - Node.js: `package.json` (npm/yarn/pnpm)
   - Java: `pom.xml` (Maven) or `build.gradle`
   - Go: `go.mod`
   - Python: `pyproject.toml` or `requirements.txt`
   - .NET: `*.csproj`

2. For each **direct** dependency, determine the latest stable version:
   - Respect semantic versioning: prefer patch/minor upgrades within the same major
   - Flag any major version bumps that may include breaking changes
   - Skip pre-release/alpha/beta versions unless the current version is also pre-release

3. Update the manifest file(s) with the new versions

4. Review the Dockerfile base image tags and suggest updated versions:
   - Check for newer patch/minor versions of the current base image
   - Flag if the base image itself has a newer LTS version available

5. Identify any upgrade that requires code changes:
   - API deprecations or removals in major bumps
   - Configuration format changes
   - Import path changes (common in Go major versions)

6. Summarize:
   - List of upgrades applied (dependency → old version → new version)
   - Breaking changes requiring code updates
   - Dependencies intentionally left at current version and why

Do not modify lock files directly — instruct the developer to run the appropriate lock command after reviewing the proposed changes.
