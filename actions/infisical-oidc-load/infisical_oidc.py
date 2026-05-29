#!/usr/bin/env python3
"""Fetch Infisical secrets via GitHub OIDC and export to GITHUB_ENV."""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# Infisical secret key -> GitHub Actions env name (must match [A-Z_][A-Z0-9_]*)
ENV_ALIASES: dict[str, str] = {
    "ansible-ssh-private-key": "ANSIBLE_SSH_PRIVATE_KEY",
    "ansible-ssh-public-key": "ANSIBLE_SSH_PUBLIC_KEY",
    "haproxy_stats_password": "HAPROXY_STATS_PASSWORD",
    "haproxy_stats_user": "HAPROXY_STATS_USER",
    "ansible_inventory": "ANSIBLE_INVENTORY",
}


def env_name_for_secret(key: str) -> str:
    if key in ENV_ALIASES:
        return ENV_ALIASES[key]
    normalized = re.sub(r"[^a-zA-Z0-9_]", "_", key).upper()
    if normalized and normalized[0].isdigit():
        normalized = f"INFISICAL_{normalized}"
    return normalized


def append_github_env(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_ENV")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        if "\n" in value or "\r" in value:
            fh.write(f"{name}<<EOF\n{value.rstrip(chr(10))}\nEOF\n")
        else:
            escaped = value.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
            fh.write(f"{name}={escaped}\n")
    print(f"::add-mask::{value}")


def main() -> int:
    domain = os.environ["INFISICAL_DOMAIN"].rstrip("/")
    identity_id = os.environ["IDENTITY_ID"]
    env_slug = os.environ["ENV_SLUG"]
    project_slug = os.environ["PROJECT_SLUG"]
    project_id = os.environ.get("PROJECT_ID", "").strip()
    secret_path = os.environ["SECRET_PATH"]
    recursive = os.environ.get("RECURSIVE", "true").lower() in ("1", "true", "yes")
    jwt_path = os.environ["JWT_FILE"]

    jwt = Path(jwt_path).read_text(encoding="utf-8").strip()
    b64 = jwt.split(".")[1]
    b64 += "=" * (-len(b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(b64))
    keys = ("sub", "aud", "iss", "repository", "ref", "environment", "workflow_ref", "job_workflow_ref")
    claims = {k: payload.get(k) for k in keys}
    print("::notice title=OIDC claims for Infisical::Set Subject and Audiences to these exact values:")
    print(json.dumps(claims, indent=2))

    login_body = urllib.parse.urlencode({"identityId": identity_id, "jwt": jwt}).encode()
    login_req = urllib.request.Request(
        f"{domain}/api/v1/auth/oidc-auth/login",
        data=login_body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(login_req) as resp:
            login_json = json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        print(f"::error::Infisical OIDC login failed ({exc.code}): {body}", file=sys.stderr)
        hint = "Check Subject and Audiences against sub/aud above."
        if "claim not allowed" in body.lower():
            hint = (
                "Subject/Audience matched; failure is in Infisical **Claims**. "
                "Remove all rows under Claims and Claim metadata mapping."
            )
        elif "subject not allowed" in body.lower():
            hint = "Set Subject to sub above, or repo:*-alexson/* on v0.160.4+."
        elif "audience not allowed" in body.lower():
            hint = "Set Audiences to aud above, or https://github.com/*-alexson."
        print(f"::error::{hint}", file=sys.stderr)
        return 1

    token = login_json.get("accessToken")
    if not token:
        print(f"::error::No accessToken in response: {login_json}", file=sys.stderr)
        return 1

    if not project_id:
        slug_req = urllib.request.Request(
            f"{domain}/api/v1/projects/slug/{urllib.parse.quote(project_slug, safe='')}",
            headers={"Authorization": f"Bearer {token}"},
        )
        try:
            with urllib.request.urlopen(slug_req) as resp:
                project_json = json.load(resp)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            print(f"::error::Project '{project_slug}' lookup failed ({exc.code}): {body}", file=sys.stderr)
            if "ProjectMembershipNotFound" in body or "not a member of this project" in body:
                print(
                    "::error::Add the machine identity under Project → Settings → Access Control → Machine Identities.",
                    file=sys.stderr,
                )
            return 1
        project_id = project_json.get("id") or project_json.get("_id") or ""
        if not project_id:
            print(f"::error::Project lookup returned no id: {project_json}", file=sys.stderr)
            return 1
        print(f"::notice::Resolved project slug '{project_slug}' -> {project_id}")

    params = urllib.parse.urlencode(
        {
            "secretPath": secret_path,
            "environment": env_slug,
            "projectId": project_id,
            "includeImports": "true",
            "recursive": "true" if recursive else "false",
            "expandSecretReferences": "true",
            "viewSecretValue": "true",
        }
    )
    secrets_req = urllib.request.Request(
        f"{domain}/api/v4/secrets/?{params}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(secrets_req) as resp:
            secrets_json = json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        print(f"::error::Infisical secrets export failed ({exc.code}): {body}", file=sys.stderr)
        return 1

    values: dict[str, str] = {s["secretKey"]: s["secretValue"] for s in secrets_json.get("secrets", [])}
    for imp in reversed(secrets_json.get("imports") or []):
        for s in imp.get("secrets") or []:
            values.setdefault(s["secretKey"], s["secretValue"])

    if not values:
        print(
            f"::error::No secrets returned for project={project_id} environment={env_slug} "
            f"secretPath={secret_path} recursive={recursive}.",
            file=sys.stderr,
        )
        return 1

    print(f"::notice::Secret keys: {', '.join(sorted(values.keys()))}")

    for key, value in values.items():
        append_github_env(env_name_for_secret(key), value)
    print(f"::notice::Loaded {len(values)} secret(s) into job environment variables")

    return 0


if __name__ == "__main__":
    sys.exit(main())
