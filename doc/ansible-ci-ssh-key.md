# Ansible SSH authentication in GitHub Actions

Standard pattern for workflows that run `ansible-playbook` on self-hosted runners.

## Preferred: SSH user certificates (short-lived)

Use the composite action to load the automation private key, sign a short-lived OpenSSH user certificate with the eh168 SSH user CA, and configure Ansible/SSH clients.

```yaml
permissions:
  id-token: write
  contents: read

steps:
  - uses: actions/checkout@v5

  - name: Prepare Ansible SSH user certificate
    uses: automation-alexson/.github-private/actions/ansible-ssh-cert-prep@v1
    with:
      signing_project_id: fca9f329-3988-40f8-a695-89fde921fc4d
      principal: automation
      cert_ttl: 1h

  - name: Run Ansible playbook
    working-directory: ansible
    env:
      ANSIBLE_PRIVATE_KEY_FILE: ${{ env.ANSIBLE_SSH_PRIVATE_KEY_FILE }}
      ANSIBLE_SSH_COMMON_ARGS: ${{ env.ANSIBLE_SSH_COMMON_ARGS }}
    run: |
      set +x
      set -euo pipefail
      test -f "${ANSIBLE_SSH_PRIVATE_KEY_FILE}"
      test -f "${ANSIBLE_SSH_CERTIFICATE_FILE}"
      ansible-playbook playbook.yml -e ansible_user=automation

  - name: Remove Ansible SSH cert and key files
    if: always()
    uses: automation-alexson/.github-private/actions/ansible-ssh-cert-cleanup@v1
```

Fleet VMs must trust the CA (`infrastructure-alexson/ssh-ca-trust` **Deploy SSH CA trust** workflow) and allow principal `automation` via `AuthorizedPrincipalsFile`.

### Composite inputs

| Input | Default | Meaning |
|-------|---------|---------|
| `signing_project_id` | (required) | Infisical project UUID for `ssh-user-ca-private-key` |
| `principal` | `automation` | OpenSSH cert principal (`-n`) |
| `cert_ttl` | `1h` | Validity passed to `ssh-keygen -V` |
| `cert_identity` | `gha-<run_id>` | Certificate identity (`-I`) |

### Infisical layout

| Secret | Project | Path |
|--------|---------|------|
| `ansible-ssh-private-key` | `secrets-vi-5-a` | `/Ansible` |
| `ssh-user-ca-private-key` | `ssh-ca-signing-0i-ei` | `/` |

See [ssh-ca-trust doc/infisical-secrets.md](https://github.com/infrastructure-alexson/ssh-ca-trust/blob/main/doc/infisical-secrets.md).

## Legacy: static private key only

Use when fleet trust is not yet deployed. Load only `/Ansible/ansible-ssh-private-key`:

```yaml
- uses: automation-alexson/.github-private/actions/infisical-oidc-load@v1
  with:
    secret_path: /Ansible
    recursive: "false"
    secret_keys: ansible-ssh-private-key
```

Then write a temp key file, run Ansible, delete the file (below).

## Write key file → run Ansible → delete file

Never pass key material on the `ansible-playbook` command line. Write a temp file, point Ansible at it, then remove it.

### 1. Write SSH private key file from GITHUB_ENV

Only needed for **legacy** flows (cert prep writes the key file automatically).

```yaml
- name: Write SSH private key file from GITHUB_ENV
  run: |
    set +x
    set -euo pipefail
    umask 077
    key="${ANSIBLE_SSH_PRIVATE_KEY:-}"
    if [ -z "$key" ]; then
      echo "::error::ANSIBLE_SSH_PRIVATE_KEY is not set."
      exit 1
    fi
    key_file="${RUNNER_TEMP}/ansible-automation-key"
    printf '%s\n' "$key" > "$key_file"
    chmod 600 "$key_file"
    echo "ANSIBLE_SSH_PRIVATE_KEY_FILE=${key_file}" >> "$GITHUB_ENV"
```

- Path: **`${RUNNER_TEMP}/ansible-automation-key`** (not `~/.ssh`, not the repo tree).
- Permissions: `umask 077`, file mode `600`.
- Use `set +x` so bash trace does not log env vars.

### 2. Run Ansible playbook

With certificates, set **`ANSIBLE_SSH_COMMON_ARGS`** so Ansible passes `CertificateFile` to SSH.

```yaml
- name: Run Ansible playbook
  working-directory: ansible
  env:
    ANSIBLE_PRIVATE_KEY_FILE: ${{ env.ANSIBLE_SSH_PRIVATE_KEY_FILE }}
    ANSIBLE_SSH_COMMON_ARGS: ${{ env.ANSIBLE_SSH_COMMON_ARGS }}
  run: |
    set +x
    set -euo pipefail
    test -f "${ANSIBLE_SSH_PRIVATE_KEY_FILE}"
    ansible-playbook playbook.yml \
      -e ansible_user=automation \
      ...
```

`ANSIBLE_PRIVATE_KEY_FILE` is Ansible’s supported env var (same as `ansible_ssh_private_key_file`). Do **not** use `-e ansible_ssh_private_key_file=...` unless you must override per play.

### 3. Remove CI SSH material

With certificates:

```yaml
- name: Remove Ansible SSH cert and key files
  if: always()
  uses: automation-alexson/.github-private/actions/ansible-ssh-cert-cleanup@v1
```

Legacy key-only cleanup:

```yaml
- name: Remove CI SSH private key file
  if: always()
  run: |
    set +x
    f="${ANSIBLE_SSH_PRIVATE_KEY_FILE:-}"
    if [ -n "$f" ] && [ -f "$f" ]; then
      shred -u "$f" 2>/dev/null || rm -f "$f"
    fi
```

## Reference implementations

- Cert auth: [`haproxy-rocky9` deploy workflow](https://github.com/infrastructure-alexson/haproxy-rocky9/blob/main/.github/workflows/deploy-haproxy.yml)
- Fleet trust deploy (static key until cutover): [`ssh-ca-trust` deploy workflow](https://github.com/infrastructure-alexson/ssh-ca-trust/blob/main/.github/workflows/deploy-ssh-ca-trust.yml)

## Env var summary

| Variable | Meaning |
|----------|---------|
| `ANSIBLE_SSH_PRIVATE_KEY` | Key material from Infisical |
| `ANSIBLE_SSH_PRIVATE_KEY_FILE` | Absolute path to the temp private key file |
| `ANSIBLE_SSH_CERTIFICATE_FILE` | Signed `*-cert.pub` (cert prep only) |
| `ANSIBLE_SSH_COMMON_ARGS` | `-o CertificateFile=... -o IdentitiesOnly=yes` |
| `ANSIBLE_PRIVATE_KEY_FILE` | Set on the playbook step; Ansible reads this |
| `SSH_USER_CA_PRIVATE_KEY` | CA signer (cert prep / issue workflows only) |

## Do not

- Commit key files or write under the checkout directory.
- Log key material (`echo`, `set -x`, multiline `::add-mask::` with embedded newlines).
- Use a separate job to load Infisical secrets (`GITHUB_ENV` does not cross jobs).
- Fetch all project secrets when only specific keys are needed (`secret_keys` allowlist).
- Store the CA private key in the main Infisical project (`secrets-vi-5-a`).
