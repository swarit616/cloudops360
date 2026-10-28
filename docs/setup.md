# Setup (Windows 11 + WSL2 Ubuntu 24.04 + Docker Desktop + VS Code)

## 1. One-time Windows/WSL preparation

1. Install WSL2 and Ubuntu 24.04 (PowerShell as admin): `wsl --install -d Ubuntu-24.04`
2. Install Docker Desktop, then **Settings -> Resources -> WSL integration -> enable "Ubuntu-24.04"**.
3. Install VS Code and the **WSL** extension; open the project with `code .` from inside Ubuntu.
4. **Keep the repository in the Linux filesystem** (`~/projects/cloudops360`), not under `/mnt/c/...`. File access
   is much faster and Linux permissions and line endings behave correctly.
5. Inside Ubuntu: `sudo apt update && sudo apt install -y python3-venv python3-pip make curl unzip git`

Optional (only needed for the matching feature):

* **systemd in WSL** (for the service-remediation demo): add to `/etc/wsl.conf`
  ```
  [boot]
  systemd=true
  ```
  then `wsl --shutdown` in PowerShell and reopen Ubuntu.
* **Terraform**: https://developer.hashicorp.com/terraform/install (HashiCorp apt repository for Ubuntu)
* **AWS CLI v2**: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
* **Azure CLI**: `curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash`

## 2. Get the code and run it

```bash
unzip cloudops360.zip && cd cloudops360      # or: git clone <your repo>
chmod +x scripts/*.sh
./scripts/setup.sh                            # venv + deps + .env  (same as: make install)
make test                                     # no cloud account needed
make run                                      # http://127.0.0.1:8000/docs
```

Without `make`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
cp .env.example .env
.venv/bin/python -m pytest
.venv/bin/uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

Windows browsers reach WSL services at `localhost`, so open http://127.0.0.1:8000/docs from Windows.

## 3. Run the full stack with Docker

```bash
cp .env.example .env          # optional; defaults work. Set GRAFANA_ADMIN_PASSWORD.
docker compose up -d --build
docker compose ps             # all four services should become "healthy"
./scripts/health_check.sh
docker compose down           # stop (data volumes are kept)
```

| Service | URL |
|---|---|
| CloudOps360 API + Swagger UI | http://127.0.0.1:8000 and http://127.0.0.1:8000/docs |
| Prometheus | http://127.0.0.1:9090 (check **Status -> Targets**) |
| Grafana | http://127.0.0.1:3000 (login from `.env`, dashboard is provisioned automatically) |
| Node Exporter | internal only (`node-exporter:9100`) |

## 4. Try the remediation demo

```bash
mkdir -p /tmp/cloudops360 && cd /tmp/cloudops360
for i in 1 2 3; do head -c 5M /dev/urandom > "old-$i.tmp"; touch -d '3 days ago' "old-$i.tmp"; done
# Force the "disk high" condition for a demo by lowering the threshold:
DISK_THRESHOLD=1 make run          # in the project directory

curl -s -X POST localhost:8000/api/remediation/dry-run | python3 -m json.tool   # preview only
```

To execute for real (local only, never on a machine you care about without reading `docs/security.md`):

```bash
export REMEDIATION_API_KEY=$(openssl rand -hex 32)
DRY_RUN=false DISK_THRESHOLD=1 make run
curl -s -X POST localhost:8000/api/remediation/execute \
  -H "X-API-Key: $REMEDIATION_API_KEY" -H 'Content-Type: application/json' \
  -d '{"confirm": true, "actions": ["disk_cleanup"]}' | python3 -m json.tool
```

Service demo (needs systemd): `sudo cp scripts/cloudops-demo.service /etc/systemd/system/`, `sudo systemctl daemon-reload`,
`sudo systemctl start cloudops-demo`, then `sudo systemctl stop cloudops-demo` and call dry-run. Executing the
restart needs privileges; see `docs/security.md` for a narrowly scoped sudoers/polkit rule instead of running as root.
Inside the Docker container there is no systemd, so service state shows as `unavailable` and nothing is restarted.

## 5. Terraform (validate only)

```bash
make terraform-check
# or per cloud:
cd terraform/aws
terraform init -backend=false
terraform fmt -recursive
terraform validate
terraform plan        # needs AWS credentials; for Azure also set admin_ssh_public_key
```

`apply` is never run by CI or any script. See `docs/aws.md` and `docs/azure.md` for cost notes and `terraform destroy`.
