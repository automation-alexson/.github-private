# automation-alexson/.github-private

Shared **composite GitHub Actions** and docs for Alexson orgs (`infrastructure-alexson`, `general-alexson`, etc.).

| Action | Purpose |
|--------|---------|
| [`infisical-oidc-load`](../actions/infisical-oidc-load) | Infisical secrets via GitHub OIDC |
| [`ansible-ssh-cert-prep`](../actions/ansible-ssh-cert-prep) | Issue short-lived SSH user certificates for Ansible |
| [`ansible-ssh-cert-cleanup`](../actions/ansible-ssh-cert-cleanup) | Remove cert key material after the job |
| [`github-app-token`](../actions/github-app-token) | Mint installation tokens for cross-repo checkout |

Docs: [`doc/infisical-oidc.md`](../doc/infisical-oidc.md) · [`doc/ansible-ci-ssh-key.md`](../doc/ansible-ci-ssh-key.md) · [`doc/github-app-automation.md`](../doc/github-app-automation.md)

**Usage:** `uses: automation-alexson/.github-private/actions/<name>@v1`
