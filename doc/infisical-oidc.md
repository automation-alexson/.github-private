# Infisical OIDC for GitHub Actions (multi-org)

Reusable workflow: [`.github/workflows/infisical-fetch.yml`](../.github/workflows/infisical-fetch.yml)

Self-hosted Infisical: `https://vault.svc.eh168.alexson.org`

## One identity for all repos

Use a **single** organization machine identity with **OIDC Auth** (not Universal Auth). Add it to each Infisical project it should read (e.g. project slug `Secrets`, environment `prod`).

Callers only need:

```yaml
permissions:
  id-token: write
  contents: read

jobs:
  fetch-secrets:
    uses: infrastructure-alexson/.github-private/.github/workflows/infisical-fetch.yml@main
    # optional overrides: project_slug, env_slug, identity_id, infisical_domain
```

No per-repo Subject configuration in YAML — binding is entirely in Infisical.

## Infisical OIDC settings (both orgs)

| Field | Value |
|--------|--------|
| OIDC Discovery URL | `https://token.actions.githubusercontent.com` |
| Issuer | `https://token.actions.githubusercontent.com` |
| **Subject** | `repo:*-alexson/*` (see below) |
| **Audiences** | Two **separate** rows — not one comma-separated line |

### Subject (fix for “OIDC subject not allowed”)

Infisical’s examples use braces only for **repo names inside one org** (`repo:my-org/{app,api}:*`). A pattern like `repo:{infrastructure-alexson,general-alexson}/*:*` often **does not match** and produces **403 subject not allowed**.

Use one of these instead:

| Subject pattern | Use when |
|-----------------|----------|
| `repo:*-alexson/*` | Both orgs end with `-alexson` (recommended) |
| `repo:infrastructure-alexson/*` | Only `infrastructure-alexson` repos |
| `repo:infrastructure-alexson/haproxy-rocky9:*` | Testing one repo (copy exact `sub` from debug) |

`*` should match `:` and `/` in the subject (e.g. `repo:org/repo:ref:refs/heads/main`). **Infisical before the picomatch `bash: true` fix** (deployed here as `v0.158.0`) often rejects all `repo:…/*` globs — use an **exact** `sub` from the workflow log step **Log GitHub OIDC claims**, or upgrade `infisical_image_tag` (e.g. `v0.160.4` or newer).

Example exact values for `haproxy-rocky9` on `main` (copy from workflow log **OIDC claims for Infisical**):

| Field | Value |
|--------|--------|
| **Subject** | `repo:infrastructure-alexson/haproxy-rocky9:ref:refs/heads/main` |
| **Audiences** | `https://github.com/infrastructure-alexson` |

Do not use globs for Subject/Audience on **v0.158.0** until Infisical is upgraded.

### Audiences

Add **two audience values** as separate entries in the UI:

1. `https://github.com/infrastructure-alexson`
2. `https://github.com/general-alexson`

Do **not** put both URLs in one field separated by a comma — that is treated as a single audience string and will not match GitHub’s `aud` claim.

Infisical supports [glob patterns](https://infisical.com/docs/documentation/platform/identities/oidc-auth/general).

Tighter examples (if you want less scope later):

| Pattern | Allows |
|---------|--------|
| `repo:infrastructure-alexson/*:ref:refs/heads/*` | Only branch refs in that org |
| `repo:general-alexson/my-app:*` | One repo only |

## Audiences vs workflow

GitHub sets the JWT `aud` claim to the **repository owner** org URL by default (`https://github.com/<owner>`). Repos under `general-alexson` send a different `aud` than `infrastructure-alexson` repos — list **both** in Infisical Audiences.

You usually do **not** need `oidc-audience` on `Infisical/secrets-action` unless you intentionally use one custom audience everywhere; then set `oidc-audience` in the workflow **and** add that same value in Infisical.

## Caller requirements

1. Repository (or org) can use `.github-private` reusable workflows (**Actions access** on `.github-private`).
2. Workflow has `permissions: id-token: write`.
3. Self-hosted runner can reach `vault.svc.eh168.alexson.org` (if using default `infisical_domain`).

## Debug a failing repo

Re-run with `debug_oidc: true`:

```yaml
uses: infrastructure-alexson/.github-private/.github/workflows/infisical-fetch.yml@main
with:
  debug_oidc: true
```

Compare printed `sub` and `aud` to the Infisical identity; adjust globs if a repo lives outside those two org names.

### GitHub org OIDC customization

If **Organization → Settings → Actions → OIDC** (or per-repo OIDC customization) changes the default `sub` format, simple `repo:org/repo:*` globs will not match. Either reset to the default subject template or set Infisical **Subject** from the exact `sub` printed by `debug_oidc: true`.
