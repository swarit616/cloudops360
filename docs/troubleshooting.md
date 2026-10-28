# Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `docker: command not found` in WSL | Docker Desktop -> Settings -> Resources -> WSL integration -> enable your distro, restart the terminal. |
| `Cannot connect to the Docker daemon` | Start Docker Desktop and wait for "Engine running". |
| Port 8000/9090/3000 already in use | Stop the other process, or change the left side of the `ports` mapping in `docker-compose.yml`. |
| Prometheus target `cloudops-api` is DOWN | `docker compose logs cloudops-api`; the container must be `healthy`. Targets use Docker DNS names, so Prometheus must run in the same Compose project. |
| Grafana shows "No data" | Check Prometheus **Status -> Targets**; open the dashboard time range (last 1h); wait 30 s after first start. |
| Grafana login fails | Credentials come from `GRAFANA_ADMIN_USER/PASSWORD` **only on first start**. Reset with `docker compose down -v` (deletes dashboards edits and data volumes). |
| Node Exporter filesystem panel empty | The `/:/host:ro` mount is blocked or the metric label differs on your Docker backend; the `cloudops_*` panels are independent of it. |
| `bash\r: No such file or directory` | Windows line endings. The repo ships `.gitattributes` (LF). Fix: `sed -i 's/\r$//' scripts/*.sh`, `git config core.autocrlf input`. |
| `Permission denied: scripts/setup.sh` | `chmod +x scripts/*.sh` (zip files lose the executable bit on some tools). |
| `make: command not found` | `sudo apt install make`, or use the direct commands in `docs/setup.md`. |
| `ensurepip is not available` | `sudo apt install python3-venv`. |
| AWS shows `configured: false` | No credentials found. Check `AWS_PROFILE`, run `aws sts get-caller-identity`. In Docker, use the override file (`docker-compose.override.example.yml`). First check can take a couple of seconds on machines without an EC2 metadata service. |
| AWS `could not be verified` | Expired SSO session or wrong keys. `detail` holds the AWS error code (e.g. `ExpiredToken`). |
| Azure shows `not configured` | Set `AZURE_SUBSCRIPTION_ID` and sign in (`az login`) or provide service-principal variables. |
| Azure `could not be verified` | Wrong tenant/secret. In WSL run `az login --use-device-code`. |
| Service remediation shows state `unavailable` | No `systemctl` (Docker, or WSL without systemd). Enable systemd in `/etc/wsl.conf` or run the API directly on the host. |
| Execute returns 403 | `DRY_RUN` is still `true`, or `REMEDIATION_API_KEY` is not set. |
| Execute returns 401 | Missing/incorrect `X-API-Key` header. |
| Cleanup finds 0 files | Files must be inside `CLEANUP_DIRS`, have an allowed extension, and be older than `CLEANUP_MIN_AGE_HOURS` (use `touch -d '3 days ago'`). Unsafe directories are listed under `rejected_directories`. |
| `black --check` fails in CI | Run `make format` once and commit. |
| `terraform fmt -check` fails | Run `terraform fmt -recursive terraform` and commit. |
| CPU/memory in the API differs from Task Manager | In Docker/WSL2 you are measuring the Linux VM, not Windows. |

Logs are JSON, one object per line: `docker compose logs -f cloudops-api | jq .` (or `make run` locally). Use the
`request_id` field (also returned as the `X-Request-ID` header) to follow one request.
