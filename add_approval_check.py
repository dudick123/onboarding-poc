"""
add_approval_check.py
────────────────────────────────────────────────────────────
Adds a manual approval check to an ADO environment using the
Checks REST API directly, since this endpoint is not yet
exposed in the azure-devops Python SDK.

Called automatically by provision_tenant.py for any environment
with requires_approval: true in provisioning.yaml, but can also
be run standalone.

Usage
-----
    uv run python add_approval_check.py \\
        --ado-org     https://dev.azure.com/my-org \\
        --project     platform-tenants \\
        --env-name    app-gateway-acme-approval \\
        --approvers   user@example.com,another@example.com \\
        --pat         $ADO_PAT

Required PAT scopes
-------------------
  Environment (Read & Manage)
"""

from __future__ import annotations

import argparse
import os
import sys

import requests
from requests.auth import HTTPBasicAuth


def get_environment_id(
    ado_org: str,
    project: str,
    env_name: str,
    pat: str,
) -> int:
    """Resolve an environment name to its numeric ADO id."""
    url = f"{ado_org}/{project}/_apis/pipelines/environments"
    resp = requests.get(
        url,
        params={"name": env_name, "api-version": "7.1"},
        auth=HTTPBasicAuth("", pat),
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("count"):
        raise ValueError(f"Environment not found: {env_name!r}. Create it first.")
    return data["value"][0]["id"]


def get_user_descriptor(
    ado_org: str,
    email: str,
    pat: str,
) -> str:
    """
    Resolve a user email to the subjectDescriptor needed by the
    Approvals API. Uses the Graph API (available at vssps subdomain).
    """
    vssps_org = ado_org.replace(
        "dev.azure.com", "vssps.dev.azure.com"
    )
    url = f"{vssps_org}/_apis/graph/users"
    resp = requests.get(
        url,
        params={"subjectTypes": "msa,aad", "api-version": "7.1-preview.1"},
        auth=HTTPBasicAuth("", pat),
    )
    resp.raise_for_status()
    for user in resp.json().get("value", []):
        if user.get("mailAddress", "").lower() == email.lower():
            return user["descriptor"]
    raise ValueError(
        f"Could not resolve user descriptor for {email!r}. "
        f"Ensure the user has been added to the ADO organisation."
    )


def add_approval_check(
    ado_org: str,
    project: str,
    env_id: int,
    approver_descriptors: list[str],
    pat: str,
    instructions: str = "Platform change-control approval required.",
    timeout_minutes: int = 1440,  # 24 h
) -> None:
    """
    POST a manual approval check to the environment via the
    Checks configurations API.
    """
    url = f"{ado_org}/{project}/_apis/pipelines/checks/configurations"
    body = {
        "type": {
            # Built-in approval check type — stable well-known id
            "id": "8c6f20a7-a545-4486-9777-f762fafe0d4d",
            "name": "Approval",
        },
        "settings": {
            "approvers": [{"id": d} for d in approver_descriptors],
            "instructions": instructions,
            "blockedApprovers": [],
            "minRequiredApprovers": 1,
        },
        "timeout": timeout_minutes,
        "resource": {
            "type": "environment",
            "id": str(env_id),
        },
    }
    resp = requests.post(
        url,
        json=body,
        params={"api-version": "7.1-preview.1"},
        auth=HTTPBasicAuth("", pat),
    )
    resp.raise_for_status()
    result = resp.json()
    print(f"  ✓ Approval check added to environment (check id={result['id']})")


def main():
    parser = argparse.ArgumentParser(
        description="Add a manual approval check to an ADO environment."
    )
    parser.add_argument("--ado-org",   required=True)
    parser.add_argument("--project",   required=True)
    parser.add_argument("--env-name",  required=True)
    parser.add_argument(
        "--approvers",
        required=True,
        help="Comma-separated list of approver email addresses",
    )
    parser.add_argument("--pat", default=os.environ.get("ADO_PAT"))
    parser.add_argument(
        "--instructions",
        default="Platform change-control approval required.",
    )
    args = parser.parse_args()

    if not args.pat:
        print("ERROR: --pat is required (or set ADO_PAT env var)")
        sys.exit(1)

    emails = [e.strip() for e in args.approvers.split(",")]

    print(f"Resolving environment: {args.env_name!r}")
    env_id = get_environment_id(args.ado_org, args.project, args.env_name, args.pat)
    print(f"  environment id = {env_id}")

    print("Resolving approver descriptors...")
    descriptors = [
        get_user_descriptor(args.ado_org, email, args.pat)
        for email in emails
    ]

    add_approval_check(
        ado_org=args.ado_org,
        project=args.project,
        env_id=env_id,
        approver_descriptors=descriptors,
        pat=args.pat,
        instructions=args.instructions,
    )


if __name__ == "__main__":
    main()
