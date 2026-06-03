# Infisical OIDC for GitHub Actions (multi-org)

Hosted in **`automation-alexson/.github-private`** (shared across `infrastructure-alexson`, `general-alexson`, and other orgs).

Composite action: [`actions/infisical-oidc-load`](../actions/infisical-oidc-load)

Self-hosted Infisical: `https://vault.svc.eh168.alexson.org`

Secrets are loaded into **`GITHUB_ENV`** in the **same job** (values are masked in logs). There is no `.env` file or artifact export.

On success the action is **silent** (no notices). It writes secrets to `GITHUB_ENV` and emits `::add-mask::` workflow commands on stdout (one per line for multiline values) so GitHub redacts them in later steps—that is not optional logging. Failures print redacted `::error::` messages to stderr, including OIDC `sub`/`aud` only when login fails.

> **Note:** `GITHUB_ENV` does not carry across jobs. Call `infisical-oidc-load` in the job that runs your playbook or deploy steps—not in a separate `fetch-secrets` job.

## One identity for all repos

Use a **single** organization machine identity with **OIDC Auth** (not Universal Auth).

**Project membership (required):** OIDC only authenticates the identity at org level. You must also add that identity to each project:

1. Open project **`secrets-vi-5-a`** in Infisical.
2. **Project Settings → Access Control → Machine Identities → Add identity**.
3. Select identity `8977b274-e440-4612-9097-69faf3ecbe2a` (or your GitHub OIDC identity).
4. Assign a project role that can **read secrets** in **`prod`**.

Without this step you get `ProjectMembershipNotFound` / “not a member of this project” (403).

## Usage

```yaml
permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    steps:
      - uses: actions/checkout@v4
      - uses: automation-alexson/.github-private/actions/infisical-oidc-load@main
        with:
          secret_path: /Ansible
          recursive: "false"
          secret_keys: ansible-ssh-private-key
      # ANSIBLE_SSH_PRIVATE_KEY, etc. are available in later steps
```

Known Infisical keys are mapped to stable env names (e.g. `ansible-ssh-private-key` → `ANSIBLE_SSH_PRIVATE_KEY`). Other keys are uppercased with non-alphanumeric characters replaced by `_`.

After load, write the SSH key to a temp file and run Ansible per [ansible-ci-ssh-key.md](ansible-ci-ssh-key.md).

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

## Audiences vs workflow

GitHub sets the JWT `aud` claim to the **repository owner** org URL by default (`https://github.com/<owner>`). Repos under `general-alexson` send a different `aud` than `infrastructure-alexson` repos — list **both** in Infisical Audiences.

The action requests the OIDC token with audience `https://github.com/<repository_owner>` by default (`oidc_audience` input overrides).

## Caller requirements

1. **`automation-alexson/.github-private`** grants workflow access (**Settings → Actions → General → Access** → enterprise-wide or per consuming org). Each **consumer org** must allow actions from **`automation-alexson`** (**Organization → Settings → Actions → General**).
2. Workflow has `permissions: id-token: write`.
3. Self-hosted runner can reach `vault.svc.eh168.alexson.org` (if using default `infisical_domain`).
4. **Project access:** machine identity added to the project; the action resolves `project_slug` via `/api/v1/projects/slug/...` then reads secrets with `/api/v4/secrets/`. Pass `project_id` (UUID) to skip slug lookup.
5. **Secrets path / environment:** defaults are `env_slug: prod`, `secret_path: /`, `recursive: true`. Use `secret_keys` (comma-separated) to load only specific Infisical keys. If zero secrets load, verify the environment slug, folder path, and key names (e.g. `ansible-ssh-private-key` under `/Ansible`).

## Debug a failing run

On OIDC login failure the step logs `sub` and `aud` in the error line. Match those in the machine identity, or widen globs after v0.160.7. For other failures, check HTTP status and the redacted API message in the log.

### GitHub org OIDC customization

If **Organization → Settings → Actions → OIDC** changes the default `sub` format, simple `repo:org/repo:*` globs will not match. Reset to the default subject template or set Infisical **Subject** from the `sub` in the login error.
