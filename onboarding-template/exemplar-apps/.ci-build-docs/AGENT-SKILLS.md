# Agent Skills — CI Build Repo

This repository ships with a set of Claude Code skills tailored to common build-repo tasks. Skills are stored in `.agents/skills/` and invoked from within Claude Code.

## How to use a skill

Open Claude Code in this repository and type `/skill-name`. Claude will read the skill definition and execute it against the current state of the repo.

```
# In Claude Code:
/security-audit
/add-healthcheck
/upgrade-dependencies
/multi-stage-dockerfile
/grill-me
```

---

## Available skills

### `/security-audit`

**When to use:** Before cutting a release, after adding a new dependency, or as part of a periodic review.

Audits the Dockerfile, dependency manifest, and source code for security weaknesses. Produces a prioritized finding list (CRITICAL / HIGH / MEDIUM / LOW) with file:line references and concrete remediation steps. Checks include:
- Non-root runtime USER in Dockerfile
- Pinned base image tags (no `latest`)
- No embedded secrets in ENV/ARG
- Dependency CVEs and abandoned packages
- Hardcoded credentials in source
- Unsafe TLS configuration

---

### `/upgrade-dependencies`

**When to use:** Monthly dependency refresh, or when a CVE advisory references one of your dependencies.

Identifies all direct dependencies in the manifest file, checks for newer stable versions (respecting semver), and proposes updated versions. Flags major-version bumps that may include breaking changes. Also reviews Dockerfile base image tags for newer versions.

Does not modify lock files — you run the appropriate lock command after reviewing the proposed changes.

---

### `/add-healthcheck`

**When to use:** When your Kubernetes deployment needs liveness/readiness probes, or when onboarding a new application type.

Reviews the Dockerfile's runtime stage and source code, then adds a `HEALTHCHECK` instruction with appropriate `--interval`, `--timeout`, `--start-period`, and `--retries` values for the runtime type. If a `/health` endpoint does not exist, it adds one that returns HTTP 200 with `{"status":"ok"}`.

---

### `/multi-stage-dockerfile`

**When to use:** When optimizing image size, improving build cache efficiency, or when the current Dockerfile does not follow multi-stage best practices.

Reviews the Dockerfile against multi-stage build best practices: stage naming, minimal runtime image, non-root USER, `.dockerignore` coverage, layer ordering for cache efficiency, and build-secret isolation. Proposes an improved Dockerfile with explanation of each change.

---

### `/grill-me`

**When to use:** When you have a design decision to make — e.g., choosing a base image strategy, deciding whether to add a feature, or planning a refactor.

Runs a relentless Socratic interview to pressure-test your thinking. Asks probing questions about assumptions, edge cases, failure modes, and tradeoffs. Does not let weak answers pass. Useful for flushing out problems before writing code.

---

## Adding your own skills

Create a new directory under `.agents/skills/` with a `SKILL.md` file:

```
.agents/skills/
  my-skill/
    SKILL.md
```

The YAML front matter sets the skill name and description:

```markdown
---
name: my-skill
description: What this skill does.
---

Instructions for Claude to follow when this skill is invoked.
```

Invoke it with `/my-skill` in Claude Code.
