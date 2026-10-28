# Security

## Threat model in one paragraph

CloudOps360 reads system and cloud state and can, optionally, change the host. The main risks are: an attacker (or a
bug) turning the remediation API into remote code execution or data deletion, credentials leaking, and the service
itself being exposed. The design removes capability rather than trying to filter bad input.

## Remediation safety (the important part)

| Control | How it is enforced |
|---|---|
| **Dry-run by default** | `DRY_RUN=true`. `/api/remediation/dry-run` never changes anything, even when `DRY_RUN=false`. |
| **No arbitrary commands** | The request model forbids unknown fields (`extra="forbid"`); `actions` is an enum of four values. There is no field that can carry a command, path or script. |
| **Fixed command templates** | The only subprocesses are `systemctl show <svc>` and `systemctl restart <svc>`, built from a validated name, `shell=False`. |
| **Service allowlist** | A service must appear in `ALLOWED_SERVICES` (operator config) and match `^[A-Za-z0-9_.@-]{1,64}$`. |
| **Cleanup allowlist** | Only `CLEANUP_DIRS` (operator config). `/`, `/etc`, `/usr`, `/var`, `/var/log`, `/home/<user>`, `/tmp` itself, and anything resolving there via `..` or symlinks are refused (`safety.py`). |
| **Conservative file rules** | Regular files only (never symlinks), allow-listed extensions, older than `CLEANUP_MIN_AGE_HOURS`, capped by `CLEANUP_MAX_FILES`, re-checked immediately before deletion. |
| **Condition-gated** | Execution only happens if the triggering issue is currently detected (service still inactive/failed, disk still above threshold). |
| **Report-only for CPU/memory** | Top consumers are reported; **no process is ever killed**. |
| **Execution is a separate, guarded endpoint** | `POST /api/remediation/execute` needs `DRY_RUN=false`, `REMEDIATION_API_KEY` configured, a matching `X-API-Key` (constant-time compare) and `confirm=true`. |
| **Verification and audit** | Every result includes before/after verification and is logged as a structured `remediation.result` event and counted in `cloudops_remediation_actions_total`. |
| **One run at a time** | A lock serialises remediation runs. |

Known limits: the file delete has a small time-of-check/time-of-use window (mitigated by re-validation and by
operating only inside dedicated directories). The API has no user accounts; the API key is a shared secret.

## Hardening for anything beyond a laptop

* Bind to localhost or put the API behind an authenticating reverse proxy / private network. The read-only endpoints
  expose process names, user names and host details.
* Run the process as a dedicated user. For service restarts, grant only that user a narrow rule instead of root, e.g.
  `/etc/sudoers.d/cloudops360`: `cloudops ALL=(root) NOPASSWD: /bin/systemctl restart cloudops-demo` (and call
  `sudo systemctl` via a small wrapper), or a polkit rule for that single unit.
* Keep `DRY_RUN=true` in production until alerts and dry-run output have been reviewed for weeks; add change windows,
  rate limits, and a human approval step (see interview guide).

## Secrets

* No secrets in code, images or Git. `.env`, key files, `*.tfvars` and state are git-ignored; `.env.example` is blank.
* Cloud access uses the SDK credential chains (roles, SSO, `az login`, managed identity) in preference to long-lived keys.
* The logger redacts values under keys like `password`, `token`, `secret`, `api_key`, `access_key`, `authorization` and
  anything shaped like an AWS access key id or bearer token. Exceptions are logged by type only.
* Cloud account and subscription ids are masked in API output. Error messages returned to clients are generic.

## Containers

Non-root user (uid 10001), read-only root filesystem with a small `tmpfs` for `/tmp`, all capabilities dropped,
`no-new-privileges`, ports bound to `127.0.0.1`, slim base image, health checks, `.dockerignore` excluding secrets.
Node Exporter mounts the host root read-only (`/:/host:ro`) to read host filesystem metrics; remove the
`--path.rootfs` flag and mount if you do not need host filesystem panels.

## Least privilege for cloud

AWS: the 7-action read-only policy in `docs/aws.md`. Azure: built-in **Reader**. Terraform defaults deny SSH from the
internet and refuse `0.0.0.0/0` in `allowed_ssh_cidrs`; EC2 requires IMDSv2 and encrypted volumes.

## CI checks

ruff (incl. flake8-bandit rules), bandit, pip-audit (advisory), Trivy image and IaC scans (report-only),
shellcheck, `terraform validate`. Tighten Trivy to `exit-code: "1"` once the baseline is clean.
