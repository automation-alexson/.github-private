# Infisical OIDC for GitHub Actions (multi-org)

Reusable workflow: [`.github/workflows/infisical-fetch.yml`](../.github/workflows/infisical-fetch.yml)

Self-hosted Infisical: `https://vault.svc.eh168.alexson.org`

## One identity for all repos

Use a **single** organization machine identity with **OIDC Auth** (not Universal Auth).

**Project membership (required):** OIDC only authenticates the identity at org level. You must also add that identity to each project:

1. Open project **`secrets-vi-5-a`** in Infisical.
2. **Project Settings → Access Control → Machine Identities → Add identity**.
3. Select identity `8977b274-e440-4612-9097-69faf3ecbe2a` (or your GitHub OIDC identity).
4. Assign a project role that can **read secrets** in **`prod`**.

Without this step you get `ProjectMembershipNotFound` / “not a member of this project” (403).

Callers only need:

```yaml
permissions:
  id-token: write
  contents: read

jobs:
  fetch-secrets:
    uses: infrastructure-alexson/.github-private/.github/workflows/infisical-fetch.yml@main
    # optional overrides: project_id (UUID), project_slug, env_slug, identity_id, infisical_domain
```

No per-repo Subject configuration in YAML — binding is entirely in Infisical.

## Infisical OIDC settings (both orgs)

| Field | Value |
|--------|--------|
| OIDC Discovery URL | `https://token.actions.githubusercontent.com` |
| Issuer | `https://token.actions.githubusercontent.com` |
| **Subject** | `repo:*-alexson/*` |
| **Audiences** | `https://github.com/*-alexson` (glob) or two exact org URLs (see below) |

Requires **Infisical v0.160.4+** (`infisical_image_tag: v0.160.7` in `infisical-microk8s`) so `*` matches `/` in GitHub `sub` claims. On **v0.158.x**, globs fail — use exact `sub`/`aud` from the workflow log until upgraded.

### Error messages (v0.160.x)

| API message | Infisical field to fix |
|-------------|-------------------------|
| `OIDC subject not allowed` | **Subject** |
| `OIDC audience not allowed` | **Audiences** |
| `OIDC claim not allowed` | **Claims** (additional JWT fields — clear this section if you only use Subject/Audience) |
| `token has no <field> field` | **Claims** or **Claim metadata mapping** references a claim not in the token |

For GitHub Actions, leave **Claims** and **Claim metadata mapping** empty unless you intentionally restrict on `repository`, `ref`, `workflow_ref`, etc.

### Subject

| Subject pattern | Use when |
|-----------------|----------|
| `repo:*-alexson/*` | All repos in `infrastructure-alexson` and `general-alexson` (recommended) |
| `repo:infrastructure-alexson/*` | One org only |
| `repo:infrastructure-alexson/haproxy-rocky9:ref:refs/heads/main` | Single branch (debug / lockdown) |

Avoid `repo:{infrastructure-alexson,general-alexson}/*:*` — brace groups across org names often do not match.

### Audiences

Either one glob:

```text
https://github.com/*-alexson
```

Or two **separate** rows (not comma-separated in one field):

1. `https://github.com/infrastructure-alexson`
2. `https://github.com/general-alexson`

Infisical supports [glob patterns](https://infisical.com/docs/documentation/platform/identities/oidc-auth/general).

Tighter examples (if you want less scope later):

| Pattern | Allows |
|---------|--------|
| `repo:infrastructure-alexson/*:ref:refs/heads/*` | Only branch refs in that org |
| `repo:general-alexson/my-app:*` | One repo only |

## Audiences vs workflow

GitHub sets the JWT `aud` claim to the **repository owner** org URL by default (`https://github.com/<owner>`). Repos under `general-alexson` send a different `aud` than `infrastructure-alexson` repos — list **both** in Infisical Audiences.

The reusable workflow sets `oidc-audience` to `https://github.com/<repository_owner>` automatically.

## Caller requirements

1. Repository (or org) can use `.github-private` reusable workflows (**Actions access** on `.github-private`).
2. Workflow has `permissions: id-token: write`.
3. Self-hosted runner can reach `vault.svc.eh168.alexson.org` (if using default `infisical_domain`).
4. **Project access:** machine identity added to the project; on Infisical **v0.160+** the workflow resolves `project_slug` via `/api/v1/projects/slug/...` then exports with `/api/v4/secrets/`. If slug lookup 404s, pass `project_id` (UUID from the project URL in the Infisical UI).

## Debug a failing repo

Re-run the workflow; the **Fetch secrets from Infisical via OIDC** step prints **OIDC claims for Infisical** (`sub`, `aud`, …) before login. Match those values in the machine identity, or widen globs after v0.160.7.

### GitHub org OIDC customization

If **Organization → Settings → Actions → OIDC** (or per-repo OIDC customization) changes the default `sub` format, simple `repo:org/repo:*` globs will not match. Either reset to the default subject template or set Infisical **Subject** from the exact `sub` printed by `debug_oidc: true`.
