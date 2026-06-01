# GitHub App for cross-repo Actions and automation

Use a **GitHub App** instead of long-lived PATs when workflows in one repo must clone or read private repos in the same org (or another org after install).

Register **one app per organization** (`infrastructure-alexson` and `general-alexson` are separate registrations). Reuse the same name and permissions on both.

## Architecture

```text
infrastructure-alexson          general-alexson
  GitHub App (App ID #1)          GitHub App (App ID #2)
  installed on infra repos        installed on general repos
         │                                │
         └─ workflows mint ~1h token ─────┘
```

- **observability** cloning **grafana-prometheus** (same org): use the **infrastructure-alexson** app with `repositories: grafana-prometheus`.
- Workflows in **general-alexson** use that org’s app ID and private key.

Alternatively, install the **infrastructure** app on **general-alexson** (one registration, two installs) if you prefer a single App ID — only if org policy allows installing external apps.

## 1. Register the app (each org)

### Option A — Manifest URL (faster)

From the **infrastructure** monorepo (or `.github-private` clone):

```powershell
pwsh .github-private/scripts/github-app-register-url.ps1
```

Open each printed URL while logged in as an **org owner**. Complete registration, then **Install App** on the org and select repositories (or all repos).

Manifest templates:

- [github-app/manifest.infrastructure-alexson.json](../github-app/manifest.infrastructure-alexson.json)
- [github-app/manifest.general-alexson.json](../github-app/manifest.general-alexson.json)

### Option B — Manual UI

| Org | New app URL |
|-----|-------------|
| infrastructure-alexson | https://github.com/organizations/infrastructure-alexson/settings/apps/new |
| general-alexson | https://github.com/organizations/general-alexson/settings/apps/new |

Suggested settings:

| Field | Value |
|-------|--------|
| Name | `Alexson Automation` |
| Homepage | `https://github.com/<org>` |
| Webhook | Disabled |
| Repository permissions → Contents | Read-only |
| Repository permissions → Metadata | Read-only |
| Where can this app be installed? | Only on this account |

After create: **Generate a private key** (download PEM once). Note the **App ID** on the app settings page.

Install the app on the org → **Only select repositories** (start with repos that need cross-clone, e.g. `grafana-prometheus`, `observability`, `.github-private`).

## 2. Store credentials

Per org, add **organization secrets** (or Infisical paths used by workflows):

| Org | Secret names |
|-----|----------------|
| infrastructure-alexson | `INFRA_GITHUB_APP_ID`, `INFRA_GITHUB_APP_PRIVATE_KEY` |
| general-alexson | `GENERAL_GITHUB_APP_ID`, `GENERAL_GITHUB_APP_PRIVATE_KEY` |

Private key: full PEM file contents including `-----BEGIN RSA PRIVATE KEY-----` lines.

Optional Infisical layout:

| Path | Keys |
|------|------|
| `/GitHub/infrastructure-alexson` | `github-app-id`, `github-app-private-key` |
| `/GitHub/general-alexson` | `github-app-id`, `github-app-private-key` |

## 3. Use in workflows

Composite action: [actions/github-app-token](../actions/github-app-token/action.yml)

```yaml
permissions:
  contents: read

steps:
  - uses: infrastructure-alexson/.github-private/actions/github-app-token@v1
    id: gh-app
    with:
      app-id: ${{ secrets.INFRA_GITHUB_APP_ID }}
      private-key: ${{ secrets.INFRA_GITHUB_APP_PRIVATE_KEY }}
      owner: infrastructure-alexson
      repositories: grafana-prometheus,observability

  - uses: actions/checkout@v5
    with:
      repository: infrastructure-alexson/grafana-prometheus
      ref: main
      path: grafana-prometheus
      token: ${{ steps.gh-app.outputs.token }}
```

For **general-alexson** repos, use `GENERAL_*` secrets and `owner: general-alexson`.

## 4. Compared to other options

| Method | When to use |
|--------|-------------|
| **GitHub App** | Many repos/workflows; short-lived tokens; org-wide standard |
| **Repo Actions access grant** | Single pair of repos, same org, no secrets |
| **PAT** | Quick one-off; avoid for long-term |

## Related

- [ansible-ci-ssh-key.md](ansible-ci-ssh-key.md) — SSH for Ansible on hosts
- [infisical-oidc.md](infisical-oidc.md) — OIDC secrets loading
- [observability doc](https://github.com/infrastructure-alexson/observability/blob/main/doc/grafana-prometheus-checkout.md) — cross-repo clone for Deploy observability
