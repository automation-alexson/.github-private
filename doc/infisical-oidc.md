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
| **Subject** | `repo:{infrastructure-alexson,general-alexson}/*:*` |
| **Audiences** | `https://github.com/infrastructure-alexson` **and** `https://github.com/general-alexson` (two entries) |

Infisical supports [glob patterns](https://infisical.com/docs/documentation/platform/identities/oidc-auth/general); `*` matches any characters including `:` and `/`. Brace groups match either org’s repos and any workflow context (`ref`, `environment`, etc.).

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
