"""
provision_tenant.py
────────────────────────────────────────────────────────────
Reads a Copier-generated provisioning.yaml AND the original
operator request file (which carries provisioned_components,
the audit record of what's already live in ADO) and drives the
Azure DevOps REST API to provision only the components that are
newly requested but not yet provisioned.

Supports iterative / phased onboarding: run once with only
include_app_gateway: true, later flip include_build_repo: true
in the same request file and re-run — only the new component
gets pushed. provisioned_components in the request file is
updated automatically after each successful run, so it always
reflects what's actually live in ADO.

Run AFTER `copier copy` (or `copier update`) has rendered/refreshed
the tenant directory from the current request file.

Usage
-----
    uv run python provision_tenant.py \\
        --tenant-dir   ./generated-tenants/tenant-acme \\
        --request-file ./onboarding-requests/tenant-acme-input.yaml \\
        --ado-org      https://dev.azure.com/my-org \\
        --pat          $ADO_PAT          # or set env var ADO_PAT

Required PAT scopes
-------------------
  Code (Read & Write), Build (Read & Execute),
  Environment (Read & Manage)
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path

import yaml
from ruamel.yaml import YAML
from azure.devops.connection import Connection
from azure.devops.v7_1.git.models import (
    GitRepositoryCreateOptions,
    GitPush,
    GitCommit,
    GitRefUpdate,
    ItemContent,
    Change,
    GitItem,
)
from azure.devops.v7_1.task_agent.models import (
    EnvironmentCreateParameter,
)
from msrest.authentication import BasicAuthentication


# ─────────────────────────────────────────────────────────────
# Connection helpers
# ─────────────────────────────────────────────────────────────

def get_clients(ado_org: str, pat: str):
    """
    Return a dict of typed ADO client objects.
    Note: pipeline registration (create_pipeline) does NOT use a typed
    SDK client — see the note above create_pipeline() for why it calls
    the REST API directly instead.
    """
    creds = BasicAuthentication("", pat)
    conn = Connection(base_url=ado_org, creds=creds)
    return {
        "git":  conn.clients.get_git_client(),
        "task": conn.clients.get_task_agent_client(),
    }


# ─────────────────────────────────────────────────────────────
# Step 1 — Create the repository
# ─────────────────────────────────────────────────────────────

def create_repo(git_client, project: str, repo_name: str) -> dict:
    """
    Create a new Git repo in the given project.
    Returns the created repo object (id, remoteUrl, etc.).
    Idempotent: if the repo already exists the API returns 409;
    we catch it and fetch the existing repo instead.
    """
    options = GitRepositoryCreateOptions(name=repo_name)
    try:
        repo = git_client.create_repository(options, project=project)
        print(f"  ✓ Created repo: {repo.name}  ({repo.remote_url})")
        return repo
    except Exception as exc:
        if "TF400948" in str(exc) or "already exists" in str(exc).lower():
            # Repo exists — fetch it
            repo = git_client.get_repository(repo_name, project=project)
            print(f"  ↩ Repo already exists, using: {repo.name}")
            return repo
        raise


# ─────────────────────────────────────────────────────────────
# Step 2 — Push the rendered file tree as an initial commit
# ─────────────────────────────────────────────────────────────

def _file_to_change(local_path: Path, repo_path: str) -> Change:
    """
    Convert a local file into a Change (add) for the push payload.
    Binary files are base64-encoded; text files use rawtext.
    """
    raw = local_path.read_bytes()
    try:
        content = raw.decode("utf-8")
        content_type = "rawtext"
    except UnicodeDecodeError:
        content = base64.b64encode(raw).decode("ascii")
        content_type = "base64Encoded"

    return Change(
        change_type="add",
        item=GitItem(path=repo_path),
        new_content=ItemContent(content=content, content_type=content_type),
    )


def push_directory(
    git_client,
    project: str,
    repo_id: str,
    source_dir: Path,
    commit_message: str = "chore: initial scaffold via copier",
) -> None:
    """
    Walk source_dir and push every file as a single initial commit.
    Only valid for a brand-new (empty) repository — oldObjectId must
    be the all-zeros SHA for the first push.
    """
    changes: list[Change] = []

    for file_path in sorted(source_dir.rglob("*")):
        if not file_path.is_file():
            continue
        # Skip Copier's own bookkeeping file — not needed in the repo
        if file_path.name == ".copier-answers.yml":
            continue
        # Repo-relative path with forward slashes, leading slash required
        relative = "/" + file_path.relative_to(source_dir).as_posix()
        changes.append(_file_to_change(file_path, relative))

    if not changes:
        print(f"  ⚠ No files found in {source_dir}, skipping push.")
        return

    push = GitPush(
        ref_updates=[
            GitRefUpdate(
                name="refs/heads/main",
                old_object_id="0000000000000000000000000000000000000000",
            )
        ],
        commits=[
            GitCommit(
                comment=commit_message,
                changes=changes,
            )
        ],
    )
    result = git_client.create_push(push, repo_id, project=project)
    print(f"  ✓ Pushed {len(changes)} file(s) — commit {result.commits[0].commit_id[:8]}")


# ─────────────────────────────────────────────────────────────
# Step 3 — Register the ADO pipeline
# ─────────────────────────────────────────────────────────────
#
# NOTE: the azure-devops Python SDK's CreatePipelineConfigurationParameters
# model in this version only types its `type` field (declared as a bare
# `object`); it does not expose typed `path` / `repository` sub-fields even
# though the live REST API accepts and requires them for a YAML pipeline.
# Rather than fight an under-typed SDK model, this function posts the
# documented JSON body directly via `requests`, using the same PAT-based
# basic auth as the rest of this script. Verify this payload shape against
# a real ADO org before relying on it in production — it has not been
# exercised against a live API in building this POC.

def create_pipeline(
    ado_org: str,
    project: str,
    pipeline_name: str,
    repo_id: str,
    yaml_path: str,
    pat: str,
) -> None:
    """
    Register a YAML pipeline pointing at yaml_path inside the repo,
    via POST {ado_org}/{project}/_apis/pipelines.
    Idempotent: lists existing pipelines first and skips creation if
    a pipeline with this name already exists.
    """
    import requests
    from requests.auth import HTTPBasicAuth

    list_url = f"{ado_org}/{project}/_apis/pipelines"
    resp = requests.get(
        list_url, params={"api-version": "7.1"}, auth=HTTPBasicAuth("", pat)
    )
    resp.raise_for_status()
    if any(p["name"] == pipeline_name for p in resp.json().get("value", [])):
        print(f"  ↩ Pipeline already exists: {pipeline_name}")
        return

    body = {
        "name": pipeline_name,
        "configuration": {
            "type": "yaml",
            "path": yaml_path,
            "repository": {
                "id": repo_id,
                "type": "azureReposGit",
            },
        },
    }
    resp = requests.post(
        list_url, json=body, params={"api-version": "7.1"}, auth=HTTPBasicAuth("", pat)
    )
    resp.raise_for_status()
    result = resp.json()
    print(f"  ✓ Created pipeline: {result['name']}  (id={result['id']})")


# ─────────────────────────────────────────────────────────────
# Step 4 — Ensure approval-gated environments exist
# ─────────────────────────────────────────────────────────────

def ensure_environment(
    task_client,
    project: str,
    env_name: str,
    requires_approval: bool,
) -> None:
    """
    Create the ADO environment if it doesn't already exist.
    Note: adding the approval check to the environment requires
    a separate Checks API call (REST only, not in Python SDK yet).
    This function creates the environment and prints a reminder
    to add the approval check manually or via the Checks REST endpoint.
    """
    try:
        envs = task_client.get_environments(project=project, name=env_name)
        if envs:
            print(f"  ↩ Environment already exists: {env_name}")
            return
    except Exception:
        pass  # get_environments raises if none found in some SDK versions

    env_param = EnvironmentCreateParameter(name=env_name)
    result = task_client.add_environment(env_param, project=project)
    print(f"  ✓ Created environment: {result.name}  (id={result.id})")

    if requires_approval:
        # The Checks API (POST _apis/pipelines/checks/configurations) is not
        # yet exposed in the Python SDK — wire the approval check here via
        # raw requests, or add it once manually through the ADO portal.
        print(
            f"  ⚠ Remember to add an approval check to environment '{env_name}' "
            f"(ADO portal → Project Settings → Environments → {env_name} → Approvals and checks)"
        )


# ─────────────────────────────────────────────────────────────
# Phase tracking — the Option 2 mechanism
# ─────────────────────────────────────────────────────────────

def load_request(request_file: Path) -> dict:
    if not request_file.exists():
        print(f"ERROR: request file not found: {request_file}")
        sys.exit(1)
    return yaml.safe_load(request_file.read_text())


def compute_delta(request: dict, provisioning_spec: dict) -> list[str]:
    """
    Returns the list of component keys (in provisioning_spec's push_order)
    that are requested (present in provisioning.yaml, since Copier already
    excluded anything with include_x: false) but not yet recorded in
    provisioned_components.
    """
    already_done = set(request.get("provisioned_components", []))
    requested = provisioning_spec["push_order"]
    delta = [c for c in requested if c not in already_done]
    return delta


def write_back_provisioned(request_file: Path, newly_done: list[str]) -> None:
    """
    Append newly successfully-provisioned component keys to
    provisioned_components and rewrite the request file using ruamel.yaml's
    round-trip mode, which preserves comments, key order, and blank lines —
    important since the request file is the audit trail (PR-reviewed
    approvals, phase notes) and shouldn't lose that context on rewrite.
    """
    ryaml = YAML()
    ryaml.preserve_quotes = True
    ryaml.indent(mapping=2, sequence=2, offset=0)

    with open(request_file) as fh:
        data = ryaml.load(fh)

    current = set(data.get("provisioned_components") or [])
    current.update(newly_done)
    data["provisioned_components"] = sorted(current)

    with open(request_file, "w") as fh:
        ryaml.dump(data, fh)

    print(f"\n  ✓ Updated {request_file} — provisioned_components now: {sorted(current)}")


# ─────────────────────────────────────────────────────────────
# Orchestrator — reads provisioning.yaml + request file,
# provisions only the delta, writes back on success
# ─────────────────────────────────────────────────────────────

def provision(tenant_dir: Path, request_file: Path, ado_org: str, pat: str) -> None:
    provisioning_file = tenant_dir / "provisioning.yaml"
    if not provisioning_file.exists():
        print(f"ERROR: {provisioning_file} not found. Run copier copy first.")
        sys.exit(1)

    spec = yaml.safe_load(provisioning_file.read_text())
    project    = spec["ado_project"]
    components = spec["components"]

    request = load_request(request_file)
    delta = compute_delta(request, spec)

    if not delta:
        print("Nothing to do — all requested components are already provisioned.")
        print(f"  provisioned_components: {request.get('provisioned_components', [])}")
        return

    print(f"Components already provisioned: {request.get('provisioned_components', []) or '(none)'}")
    print(f"Components to provision this run: {delta}\n")

    clients = get_clients(ado_org, pat)
    git_client  = clients["git"]
    task_client = clients["task"]

    succeeded: list[str] = []

    for component_key in delta:
        comp = components[component_key]
        repo_name     = comp["repo_name"]
        source_dir    = tenant_dir / comp["source_dir"]
        pipeline_yaml = comp["pipeline_yaml_path"]
        pipeline_name = comp["pipeline_name"]
        environments  = comp.get("environments", [])

        print(f"{'─'*60}")
        print(f"Component: {component_key}  →  repo: {repo_name}")
        print(f"{'─'*60}")

        try:
            repo = create_repo(git_client, project, repo_name)
            push_directory(
                git_client,
                project=project,
                repo_id=repo.id,
                source_dir=source_dir,
                commit_message=f"chore: initial scaffold for {repo_name} via copier",
            )
            create_pipeline(
                ado_org=ado_org,
                project=project,
                pipeline_name=pipeline_name,
                repo_id=repo.id,
                yaml_path=pipeline_yaml,
                pat=pat,
            )
            for env in environments:
                ensure_environment(
                    task_client,
                    project=project,
                    env_name=env["name"],
                    requires_approval=env.get("requires_approval", False),
                )
            succeeded.append(component_key)
            print(f"  ✓ {component_key} provisioned successfully.\n")
        except Exception as exc:
            print(f"  ✗ {component_key} FAILED: {exc}")
            print(f"    Not recorded in provisioned_components — re-run after fixing to retry.\n")

    if succeeded:
        write_back_provisioned(request_file, succeeded)

    failed = [c for c in delta if c not in succeeded]
    print(f"\n{'═'*60}")
    if failed:
        print(f"Provisioning run finished with failures: {failed}")
        print("Re-run the same command after addressing the error(s) above —")
        print("succeeded components will be skipped automatically.")
        sys.exit(1)
    else:
        print("Provisioning complete.")
    print(f"{'═'*60}")


# ─────────────────────────────────────────────────────────────
# CLI entrypoint
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Provision ADO repos and pipelines from a Copier-rendered tenant directory, "
                    "acting only on components not yet recorded in provisioned_components."
    )
    parser.add_argument(
        "--tenant-dir",
        required=True,
        type=Path,
        help="Path to the Copier-generated tenant directory (must contain provisioning.yaml)",
    )
    parser.add_argument(
        "--request-file",
        required=True,
        type=Path,
        help="Path to the operator request YAML (carries provisioned_components; "
             "this file is updated in place after a successful run)",
    )
    parser.add_argument(
        "--ado-org",
        required=True,
        help="Azure DevOps org URL, e.g. https://dev.azure.com/my-org",
    )
    parser.add_argument(
        "--pat",
        default=os.environ.get("ADO_PAT"),
        help="ADO Personal Access Token (or set ADO_PAT env var)",
    )
    args = parser.parse_args()

    if not args.pat:
        print("ERROR: --pat is required (or set ADO_PAT env var)")
        sys.exit(1)

    provision(args.tenant_dir, args.request_file, args.ado_org, args.pat)


if __name__ == "__main__":
    main()
