# Ansible SSH private key in GitHub Actions

Standard pattern for any workflow that runs `ansible-playbook` on self-hosted runners.

## Secrets source

Prefer **Infisical OIDC** in the **same job** as the playbook (not a separate fetch job):

```yaml
permissions:
  id-token: write
  contents: read

steps:
  - uses: infrastructure-alexson/.github-private/actions/infisical-oidc-load@v1
    with:
      secret_path: /Ansible
      recursive: "false"
      secret_keys: ansible-ssh-private-key
```

Infisical key `ansible-ssh-private-key` → env var `ANSIBLE_SSH_PRIVATE_KEY` (masked in `GITHUB_ENV`).

Legacy repos may still use org secret `AUTOMATION_SSH_KEY`; map that into the same write step below.

## Write key file → run Ansible → delete file

Never pass key material on the `ansible-playbook` command line. Write a temp file, point Ansible at it, then remove it.

### 1. Write SSH private key file from GITHUB_ENV

```yaml
- name: Write SSH private key file from GITHUB_ENV
  run: |
    set +x
    set -euo pipefail
    umask 077
    key="${ANSIBLE_SSH_PRIVATE_KEY:-}"   # or: "${AUTOMATION_SSH_KEY:-}" from secrets.*
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

```yaml
- name: Run Ansible playbook
  working-directory: ansible
  env:
    ANSIBLE_PRIVATE_KEY_FILE: ${{ env.ANSIBLE_SSH_PRIVATE_KEY_FILE }}
  run: |
    set +x
    set -euo pipefail
    test -f "${ANSIBLE_SSH_PRIVATE_KEY_FILE}"
    ansible-playbook playbook.yml \
      -e ansible_user=automation \
      ...
```

`ANSIBLE_PRIVATE_KEY_FILE` is Ansible’s supported env var (same as `ansible_ssh_private_key_file`). Do **not** use `-e ansible_ssh_private_key_file=...` unless you must override per play.

### 3. Remove CI SSH private key file

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

## Reference implementation

[`haproxy-rocky9` deploy workflow](https://github.com/infrastructure-alexson/haproxy-rocky9/blob/main/.github/workflows/deploy-haproxy.yml).

## Env var summary

| Variable | Meaning |
|----------|---------|
| `ANSIBLE_SSH_PRIVATE_KEY` | Key material from Infisical (or map from `AUTOMATION_SSH_KEY`) |
| `ANSIBLE_SSH_PRIVATE_KEY_FILE` | Absolute path to the temp key file on disk |
| `ANSIBLE_PRIVATE_KEY_FILE` | Set on the playbook step only; Ansible reads this |

## Do not

- Commit key files or write under the checkout directory.
- Log key material (`echo`, `set -x`, multiline `::add-mask::` with embedded newlines).
- Use a separate job to load Infisical secrets (`GITHUB_ENV` does not cross jobs).
- Fetch all project secrets when only the SSH key is needed (`secret_keys` allowlist).
