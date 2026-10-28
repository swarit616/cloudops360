# Interview guide

## Explain this project in 60 seconds

"CloudOps360 is a small Cloud Operations platform I built. A FastAPI service uses psutil to monitor a Linux host -
CPU, memory, disk, network, load, services - and exposes Prometheus metrics. Prometheus scrapes it and Node Exporter,
alerts on high CPU, memory, disk, load and hosts being down, and Grafana shows a provisioned dashboard. The API also
runs diagnostics and has a safe remediation engine: dry-run by default, a strict allowlist of actions, no arbitrary
commands, and verification after every action. Optional AWS and Azure adapters discover instances, disks, networks and
cloud metrics using least-privilege read-only access, and they switch off cleanly without credentials. Everything runs
locally with Docker Compose, the infrastructure is described in Terraform, and GitHub Actions lints, tests, validates
and scans every change."

## Explain this project in 2 minutes

Add to the 60-second version:

1. **The problem**: teams need one view across hosts and clouds, explanations rather than raw alerts, and automation
   that cannot become the outage.
2. **Monitoring path**: custom Prometheus collectors read psutil at scrape time, so values are fresh; cloud data is
   refreshed in a background thread and cached, so a scrape never waits on AWS or Azure.
3. **Detection and diagnostics**: thresholds come from environment variables; `detect_issues` turns a snapshot into
   typed issues; `/api/diagnostics` adds top processes and recommendations.
4. **Remediation**: four actions only - disk cleanup in configured directories, restart of an allow-listed service,
   and report-only for CPU and memory. Execution needs `DRY_RUN=false`, an API key and `confirm=true`, only acts if the
   condition still exists, and returns a verification result. Every action is logged and counted.
5. **Engineering quality**: dependency injection so tests use fakes (no cloud accounts, no systemd), structured JSON
   logs with redaction, 90+ test cases, Terraform with cost-aware defaults, CI with Terraform validate and image scans.
6. **What I'd do next**: Alertmanager, a persistent audit log, real authentication and approvals, multi-host agents.

## How would you deploy this in production?

* Run the API as a container (ECS/Fargate, AKS/EKS, or a VM) behind a private load balancer or an authenticating
  proxy; use an IAM role / managed identity so there are no keys.
* Remove the local-lab shortcuts: managed Prometheus (AMP / Azure Monitor managed Prometheus) or HA Prometheus with
  Alertmanager, Grafana with SSO, TLS everywhere, persistent volumes with backup.
* Terraform remote state (S3 + DynamoDB lock / Azure Storage), plan on pull request, apply from a protected pipeline
  with OIDC federation instead of stored secrets.
* Roll out per-host agents (or Node Exporter via Ansible/SSM) and monitor many hosts; add service discovery.
* Keep remediation in dry-run until proven; add approvals, rate limits, change windows and an audit store.
* Centralised JSON logs (CloudWatch Logs / Log Analytics / Loki), SLOs and on-call routing.

## How would you secure it?

Authenticate and authorise the API (OIDC, RBAC; separate read vs remediate roles), bind privately, TLS, least-privilege
cloud identities (Reader / the 7-action AWS policy), no long-lived keys, secret store (AWS Secrets Manager / Key
Vault), non-root read-only containers with dropped capabilities, dependency and image scanning in CI, pinned base
images, rate limiting, audit logging of every remediation, and a narrowly scoped sudoers/polkit rule instead of root.

## How would you prevent remediation from causing outages?

1. Dry-run first, always, and default to it.
2. Allowlist of actions, services and directories controlled by operators, not callers.
3. Act only if the condition still exists at execution time.
4. Conservative scope (age, extension, cap on files; never kill processes).
5. Verify after acting and report failures; stop on failure rather than retry blindly.
6. One run at a time, rate limits, cool-down periods, maintenance windows.
7. Blast-radius limits (one host/service at a time, canary hosts), approvals for risky actions.
8. Observability on the automation itself: counters by action/outcome, alerts on repeated failures.
9. Easy kill switch (`DRY_RUN=true`) and a full audit trail to review.

## Questions and answers

### AWS

**What AWS services does the project touch and why?** EC2 (instances), EBS (volumes), CloudWatch (CPU metric), VPC
(networks), STS/IAM (who am I, account alias). All read-only. Terraform adds VPC, subnet, IGW, security groups, IAM role
and an EC2 + EBS example.

**Security group vs NACL?** Security groups are stateful, attached to ENIs, allow-only. NACLs are stateless, per subnet,
allow and deny, evaluated by rule number. I use security groups for instance access and lock down the default one.

**How do EC2 instances get credentials without keys?** Instance profiles: the role is assumed through the metadata
service (IMDSv2) and boto3 picks it up via the default credential chain. I require IMDSv2 in Terraform to mitigate SSRF
credential theft.

**EBS types and encryption?** gp3 is the general default (IOPS/throughput decoupled from size). I encrypt root and data
volumes. Snapshots are the backup mechanism.

### Azure

**Azure equivalents of what you used?** EC2 -> Virtual Machines, EBS -> Managed Disks, CloudWatch -> Azure Monitor, VPC ->
VNet, security group -> NSG, IAM role -> managed identity + RBAC, account -> subscription, resource groups group lifecycle.

**What is DefaultAzureCredential?** A credential chain: environment variables, workload identity, managed identity,
Azure CLI, and more. Same code runs on a laptop (`az login`) and in Azure (managed identity).

**What role does the monitoring identity need?** Reader, scoped to the subscription or resource group. Not Contributor.

### Linux

**CPU utilisation vs load average?** Utilisation is the fraction of time CPUs are busy. Load average counts runnable plus
uninterruptible (often I/O-waiting) tasks over 1/5/15 minutes; I divide by cores. High load with low CPU suggests I/O
wait or blocked tasks.

**Disk full - how do you investigate?** `df -h` (also `df -i` for inodes), `du -xh --max-depth=1 | sort -rh`, `lsof +L1`
for deleted-but-open files, log rotation, then clean safely. `scripts/disk_check.sh` automates the first steps.

**Why not just kill the top CPU process?** It may be the production workload. Killing is high blast radius; reporting
gives a human context. That is why CPU and memory are report-only.

**How do you check/restart a service safely?** `systemctl status/show`, `journalctl -u`, then `systemctl restart` for a
named unit only, followed by verification (`is-active`).

### Networking

**What network metrics matter?** Throughput, packet errors and drops (cabling/driver/saturation), retransmits,
connection counts, latency. I export bytes, errors and drops per direction.

**How would you debug "service unreachable"?** Layer by layer: DNS (`dig`), route/ping, port (`nc -zv`, `ss -tlnp`),
firewall/security group/NSG, application logs, load balancer health checks.

**What is CIDR and why choose /16 and /24 here?** Prefix notation for address ranges. VPC /16 leaves room for subnets,
/24 gives 251 usable addresses on AWS. Ranges must not overlap with peered networks.

### IAM

**Least privilege in this project?** A 7-action AWS read-only policy and Azure Reader; no wildcard actions, no write
permissions; roles/SSO over keys. Remediation is local and separate from cloud permissions.

**IAM user vs role?** Users have long-lived credentials; roles give temporary credentials via STS and trust policies.
Prefer roles.

**How do you avoid leaking keys?** Never in code or images, `.gitignore`, secret scanning, short-lived credentials, log
redaction, rotate immediately if exposed.

### Terraform

**What do modules, variables, outputs give you?** Reuse (network/compute/iam modules), configuration without editing
code, and a published interface (ids, ARNs).

**Why `enable_ec2` / `enable_vm` flags and `count` on a module?** Cost control and ability to plan only the network.
Outputs use `one(module.compute[*].x)` so they are null when disabled.

**State?** The record of what Terraform manages. Locally it is a file (git-ignored, may contain secrets). Production:
remote backend with locking and encryption.

**fmt / validate / plan / apply?** fmt normalises style, validate checks syntax and internal consistency, plan previews
changes, apply performs them. CI runs the first two without credentials; apply is manual/protected.

### Docker

**Why non-root, read-only filesystem, dropped capabilities?** Limits damage if the app is compromised. The app only needs
a small `tmpfs` at `/tmp`.

**Why `--factory` and a health check?** The app builds without import side effects; health checks let Compose gate
dependencies (`depends_on: service_healthy`) and restart unhealthy containers.

**Why bind ports to 127.0.0.1?** The stack has no auth by default; exposing it on all interfaces would publish host
details.

### Prometheus

**Pull vs push?** Prometheus scrapes targets: simple discovery, health via `up`, no client buffering. Pushgateway only for
short-lived jobs.

**Why custom collectors?** They compute values at scrape time, so there is no stale gauge state and no background
polling thread for local metrics.

**Counter vs gauge?** Counters only go up (use `rate()`); gauges go up and down. Network bytes are counters, CPU % is a
gauge.

**Why `for: 5m` in alerts?** Avoids flapping on brief spikes; pages should reflect sustained problems.

**Label cardinality?** Each unique label set is a time series. I label by mountpoint, direction, provider and a few
states; never by request ids or user input. HTTP metrics use the route template, not the raw path.

### Grafana

**How is it provisioned?** Datasource and dashboard provider YAML under `provisioning/`, dashboard JSON on a mounted
path; no clicking needed, and it is reviewable in Git.

**Which panels would you add for an SRE team?** SLO burn rate, error budget, saturation per resource, alert history.

### Python and FastAPI

**Why FastAPI?** Type-driven validation (Pydantic), automatic OpenAPI docs, dependency injection, async support.

**Why are the route functions synchronous?** psutil and the cloud SDKs are blocking; FastAPI runs `def` routes in a
threadpool so the event loop is not blocked.

**How do you test without cloud accounts?** Dependency injection: fake collector, fake command runner, fake boto3
session and Azure clients. Plus `TestClient` for the API.

**How do you handle errors?** Domain exceptions map to HTTP codes (422 rejected, 403 disabled, 401 bad key); unexpected
errors become a generic 500 with a request id; cloud failures become `configured:false` or warnings, never crashes.

### CI/CD and GitHub Actions

**What does your pipeline do?** Lint, format check, tests (3.11/3.12), bandit, pip-audit, Terraform fmt/validate, shellcheck,
Docker build + smoke test, promtool, Trivy.

**Why no cloud credentials in CI?** Tests use fakes; Terraform validates with `-backend=false`. If deploy jobs were
added they would use OIDC federation, not stored keys.

**Why `permissions: contents: read` and `concurrency`?** Least privilege for the workflow token; cancels superseded runs.

### Monitoring and alerting

**Symptoms vs causes?** Alert on user-impacting symptoms where possible and use cause metrics (CPU, disk) for diagnosis
and capacity. My infrastructure alerts are cause-based because this is a host-monitoring tool.

**What makes a good alert?** Actionable, has a runbook link, has an owner, low false-positive rate. My annotations point
to the diagnostics endpoint and dry-run.

### Incident response

**Walk me through an incident with this tool.** Alert `HighDiskUsage` fires -> open the dashboard -> `GET /api/diagnostics`
-> `scripts/disk_check.sh` -> `POST /api/remediation/dry-run` shows files that would go -> approve execution -> verification
shows usage back under threshold -> record follow-ups (log rotation, capacity).

**What would you add for a real on-call?** Alertmanager routing, runbooks, escalation, post-incident reviews.

### Auto-remediation

**When is auto-remediation a bad idea?** Stateful systems, unclear root cause, actions that can cascade (restarting many
nodes), anything without verification or rollback.

**Why verify?** An action that "ran" is not the same as a problem that is fixed; verification catches silent failures and
drives escalation.

### Security

**How do you stop command injection?** There is no way to supply commands: schema forbids extra fields, actions are an
enum, services come from config and a strict regex, subprocesses use fixed argv with `shell=False`.

**How do you stop path traversal / deleting the wrong files?** Operator-defined directories only, normalised and
resolved paths, protected-path refusal, no symlink following or deletion, regular files with allowed extensions and age,
re-check before delete, capped count.

**Is the API key enough?** For a lab, yes (constant-time compare, off by default). Production needs real identity, RBAC
and audit.

### Cloud cost awareness

**How did you keep cost low?** t3.micro / B1s, small gp3 / Standard_LRS disks, no NAT gateway or public load balancer,
`enable_*` flags, `destroy` instructions, read-only adapters that cache results (fewer API calls; CloudWatch
`GetMetricData` is billed per metric requested).

**What are common surprise costs?** NAT gateways, idle public IPv4 addresses, unattached volumes, data transfer,
detailed monitoring, log ingestion. Tag everything, set budgets and alerts, review Cost Explorer / Cost Management.
