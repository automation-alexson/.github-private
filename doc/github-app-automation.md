# GitHub App for cross-repo Actions and automation



Use a **GitHub App** instead of long-lived PATs when workflows must clone or read private repos across repositories (same org or another org after install).



**Recommended:** register **one** app in **`automation-alexson`**, then **install** it on **`infrastructure-alexson`** and **`general-alexson`**. Workflows use the same App ID and private key; `owner` is the org where the app is installed (where the target repos live).



## Architecture



```text

automation-alexson (registers app — one App ID + one PEM)

        │

        ├── installed on infrastructure-alexson → repos: grafana-prometheus, observability, …

        └── installed on general-alexson          → repos that need cross-clone

                │

                └── workflows mint ~1h token with owner: <target-org>

```



| Concept | Value |

|---------|--------|

| App registered in | `automation-alexson` |

| App installed on | `infrastructure-alexson`, `general-alexson` (each install picks its own repos) |

| Token `owner` input | The org being accessed (`infrastructure-alexson` or `general-alexson`), **not** `automation-alexson` |

| Secrets (same values in each consumer org) | `AUTOMATION_GITHUB_APP_ID`, `AUTOMATION_GITHUB_APP_PRIVATE_KEY` |



Legacy secret names `INFRA_GITHUB_APP_*` / `GENERAL_GITHUB_APP_*` still work in workflows that reference them; prefer `AUTOMATION_*` everywhere.



## 1. Register the app (automation-alexson only)



You must be an **org owner** of `automation-alexson`.



### Option A — Manifest URL



```powershell

pwsh .github-private/scripts/github-app-register-url.ps1

```



Open the URL under `manifest.automation-alexson.json` while logged in as an **automation-alexson** org owner. Confirm the new app is **owned by automation-alexson**.



Manifest: [github-app/manifest.automation-alexson.json](../github-app/manifest.automation-alexson.json) (`public: true` so other orgs can install it).



### Option B — Manual UI



https://github.com/organizations/automation-alexson/settings/apps/new



| Field | Value |

|-------|--------|

| Name | `automation-alexson` |

| Homepage | `https://github.com/automation-alexson` |

| Webhook | Disabled |

| Repository permissions → Contents | Read-only |

| Repository permissions → Metadata | Read-only |

| Where can this GitHub App be installed? | **Any account** (required for infra + general installs) |



After create:



1. Note the numeric **App ID** (top of app settings).

2. Scroll past **Client secrets** — that section is for user OAuth, not Actions.

3. Under **Private keys** → **Generate a private key** → save the `.pem` once.



## 2. Install on infrastructure-alexson and general-alexson



From the app page: **Install App** (sidebar), or https://github.com/apps/automation-alexson/installations/new



Repeat for **each** target org:



### infrastructure-alexson



1. Choose **infrastructure-alexson** → **Install**.

2. **Repository access:** **Only select repositories** (recommended). Include at least:

   - `grafana-prometheus`

   - `observability`

   - `.github-private` (if workflows checkout it)

   - Any other private repo workflows read via the app token

3. Confirm **Install**.



### general-alexson



1. **Install App** again → choose **general-alexson**.

2. Select repos in that org that workflows need to read.



**Org policy:** if install is blocked, check **Settings → Third-party access** (or **GitHub Apps** policy) on the **target** org and allow apps from `automation-alexson` / approved third-party apps.



Optional: install on **automation-alexson** itself if runners or repos there also need cross-repo checkout.



## 3. Store credentials (consumer orgs)

### GitHub Free org / GitHub Pro personal (private repos)

**GitHub Pro** is a **personal** plan. **Organizations** stay on **GitHub Free** until you upgrade the **org** to **GitHub Team**.

On a **Free organization**, **organization secrets cannot be used by private repositories** — even if you personally have Pro.

**Use repository secrets** on each **private** repo that runs the workflow (same names and values everywhere):

| Repository | Settings → Secrets → Actions |
|------------|------------------------------|
| `infrastructure-alexson/observability` | `AUTOMATION_GITHUB_APP_ID`, `AUTOMATION_GITHUB_APP_PRIVATE_KEY` |
| Other private repos with cross-clone workflows | Same two secrets |

The GitHub App itself (register + install) **does** work on Free; only **org-level** secret sharing to private repos does not.

**No extra secrets:** use [Option C in observability doc](https://github.com/infrastructure-alexson/observability/blob/main/doc/grafana-prometheus-checkout.md) (grant `observability` access to `grafana-prometheus` Actions) — free and no PEM in GitHub.

**Paid alternative:** upgrade **infrastructure-alexson** (the org) to **GitHub Team** — not GitHub Pro on your user account.

### GitHub Team / Enterprise

Add the **same** App ID and PEM as **organization** secrets in each org where workflows run:

| Org | Organization secrets |
|-----|----------------------|
| infrastructure-alexson | `AUTOMATION_GITHUB_APP_ID`, `AUTOMATION_GITHUB_APP_PRIVATE_KEY` |
| general-alexson | `AUTOMATION_GITHUB_APP_ID`, `AUTOMATION_GITHUB_APP_PRIVATE_KEY` |

Set **Repository access** to **All repositories** or **Private repositories**.

### Infisical (recommended on Free orgs)

Store credentials once in Infisical instead of GitHub org/repo secrets:

| Path | Keys | Notes |
|------|------|--------|
| `/GitHub/automation-alexson` | `github-app-id` | Numeric App ID |
| same | `github-app-private-key` | Full PEM (multiline secret) |

Project **`secrets-vi-5-a`**, environment **`prod`**. The machine identity must read this path (same OIDC setup as `/Ansible`).

Workflows load via [infisical-oidc-load](../actions/infisical-oidc-load) → `AUTOMATION_GITHUB_APP_ID` / `AUTOMATION_GITHUB_APP_PRIVATE_KEY` in `GITHUB_ENV` (masked). **Deploy observability** loads this path before minting the app token.

Private key: full PEM including `-----BEGIN RSA PRIVATE KEY-----` / `-----END RSA PRIVATE KEY-----`.

## 4. Use in workflows

Composite action: [actions/github-app-token](../actions/github-app-token/action.yml)



**infrastructure-alexson** example (`observability` cloning `grafana-prometheus`):



```yaml

permissions:

  contents: read



steps:

  - uses: infrastructure-alexson/.github-private/actions/github-app-token@v1.1.0

    id: gh-app

    with:

      app-id: ${{ secrets.AUTOMATION_GITHUB_APP_ID }}

      private-key: ${{ secrets.AUTOMATION_GITHUB_APP_PRIVATE_KEY }}

      owner: infrastructure-alexson

      repositories: grafana-prometheus



  - uses: actions/checkout@v5

    with:

      repository: infrastructure-alexson/grafana-prometheus

      ref: main

      path: grafana-prometheus

      token: ${{ steps.gh-app.outputs.token }}

```



**general-alexson** repos: same secrets, `owner: general-alexson`, and list that org’s repo names in `repositories:`.



### Private composite actions (`.github-private`)



The app token applies to **`actions/checkout`** steps you pass it to. It does **not** replace GitHub’s resolution of `uses: org/repo/action@ref` — keep **Settings → Actions → Access** on `.github-private` for shared composite actions, or checkout `.github-private` with the app token and use `uses: ./local-path`.



## 5. Alternative — one app per org



Register separately under `infrastructure-alexson` and `general-alexson` if policy forbids cross-org installs or you want isolated App IDs:



- [manifest.infrastructure-alexson.json](../github-app/manifest.infrastructure-alexson.json) — `public: false`, only on that org

- [manifest.general-alexson.json](../github-app/manifest.general-alexson.json)



Use org-specific secret names (`INFRA_*`, `GENERAL_*`) and matching `owner`.



## 6. Compared to other options



| Method | When to use |

|--------|-------------|

| **GitHub App (this doc)** | Many repos/workflows; short-lived tokens; one registration, multiple installs |

| **Repo Actions access grant** | Single repo pair, same org, no secrets |

| **PAT** | Quick one-off; avoid long-term |



## Troubleshooting — secrets not visible to private repos

### Fix repository access (most common)

Org secrets are created with a **Repository access** policy. If only **public** repos can use them, workflows in **private** repos (e.g. `observability`) will not see `AUTOMATION_GITHUB_APP_*`.

For **each** secret in the **consumer org** (`infrastructure-alexson`, `general-alexson`):

1. **Settings** → **Secrets and variables** → **Actions**
2. Open `AUTOMATION_GITHUB_APP_ID` (repeat for `AUTOMATION_GITHUB_APP_PRIVATE_KEY`)
3. **Repository access** → choose one of:
   - **All repositories** (simplest), or
   - **Private repositories** (private + internal only), or
   - **Selected repositories** → add **`observability`**, **`grafana-prometheus`**, and every private repo that runs the workflow
4. **Save**

Do **not** leave **Selected repositories** with only public repos listed.

### Secrets must live in the workflow org

Workflows in **`infrastructure-alexson/observability`** read org secrets from **infrastructure-alexson**, not from **automation-alexson** (where the app is registered). Copy the same App ID + PEM into **infrastructure-alexson** org secrets with the access policy above.

### GitHub Free / Pro vs GitHub Team

**GitHub Pro** upgrades your **personal account**. It does **not** upgrade **organizations**.

**Organization secrets for private repos** require the **organization** to be on **GitHub Team** (or Enterprise), not GitHub Pro on your user.

| Plan | Where it applies | Org secrets → private org repos |
|------|------------------|----------------------------------|
| GitHub Free (org) | `infrastructure-alexson` | No |
| GitHub Pro (personal) | Your user account | **No** (org still on Free) |
| **GitHub Team** (org) | `infrastructure-alexson` | **Yes** |

Check: **infrastructure-alexson** → **Settings** → **Billing and plans** — it should show **Team**, not Free.

Until the org is on Team, use **repository secrets** (below) or the grafana-prometheus **Actions access grant** (no secrets).

### Fix via GitHub CLI

```bash
gh secret set AUTOMATION_GITHUB_APP_ID --org infrastructure-alexson --visibility private
gh secret set AUTOMATION_GITHUB_APP_PRIVATE_KEY --org infrastructure-alexson --visibility private
# Or explicit repos:
gh secret set AUTOMATION_GITHUB_APP_ID --org infrastructure-alexson --repos observability,grafana-prometheus
```

## Related



- [ansible-ci-ssh-key.md](ansible-ci-ssh-key.md) — SSH for Ansible on hosts

- [infisical-oidc.md](infisical-oidc.md) — OIDC secrets loading

- [observability doc](https://github.com/infrastructure-alexson/observability/blob/main/doc/grafana-prometheus-checkout.md) — cross-repo clone for Deploy observability


