# Architecture

CloudOps360 is a deliberately small version of what a Cloud Operations team runs: collect signals, detect problems,
explain them, and (carefully) fix the ones that are safe to fix.

```mermaid
flowchart TB
    subgraph Host["Linux host (WSL2 / VM / server)"]
        NE["Node Exporter :9100"]
        subgraph API["CloudOps360 API (FastAPI) :8000"]
            MON["Local monitoring (psutil)"]
            DIAG["Diagnostics + threshold detection"]
            REM["Safe remediation engine\n(allowlist, dry-run default)"]
            MET["/metrics (prometheus-client)"]
            AWS["AWS adapter (boto3)"]
            AZ["Azure adapter (azure-identity + mgmt SDKs)"]
        end
    end
    PROM["Prometheus :9090\n+ alert rules"]
    GRAF["Grafana :3000\n(provisioned dashboard)"]
    AWSC[("AWS: EC2, EBS, CloudWatch,\nVPC, IAM identity")]
    AZC[("Azure: VMs, Disks, Monitor,\nRGs, VNet/NSG")]

    NE -->|scrape| PROM
    MET -->|scrape| PROM
    PROM --> GRAF
    MON --> DIAG --> REM
    MON --> MET
    AWS -. optional, only with credentials .-> AWSC
    AZ -. optional, only with credentials .-> AZC
    AWS --> MET
    AZ --> MET
```

## Components

| Component | Responsibility | Where |
|---|---|---|
| Collector | psutil snapshot: CPU, memory, filesystems, disk I/O, network, load, uptime, processes, service state | `app/monitoring/system.py` |
| Threshold logic | Compares a snapshot with env-configured thresholds, producing typed `Issue`s | `detect_issues()` |
| Metrics | Custom Prometheus collectors evaluated at scrape time; cloud series come from cached overviews | `app/monitoring/metrics.py` |
| Remediation engine | Plans actions per issue, executes only allow-listed ones, always verifies and reports | `app/remediation/engine.py`, `safety.py` |
| Cloud adapters | Read-only discovery with graceful "not configured" behaviour, TTL cache, background refresh | `app/cloud/*` |
| API | FastAPI routers, request IDs, structured logs, consistent error bodies | `app/api/*`, `app/main.py` |

## Request flow: `POST /api/remediation/dry-run`

```mermaid
sequenceDiagram
    participant C as Client
    participant A as API
    participant E as RemediationEngine
    participant M as SystemCollector
    C->>A: POST /api/remediation/dry-run
    A->>E: run(request, execute=False)
    E->>M: snapshot()
    M-->>E: metrics + service state
    E->>E: detect_issues() -> plan (allow-listed actions only)
    E->>E: handlers preview (scan files, would-restart, top processes)
    E-->>A: RemediationReport (dry_run=true, nothing changed)
    A-->>C: 200 JSON
```

## Design decisions

* **LOCAL, AWS and AZURE are always labelled.** API models carry a `provider`; cloud Prometheus series carry a
  `provider` label; local series are unlabelled (`cloudops_*`) and cloud series are `cloudops_cloud_*`.
* **A scrape never calls a cloud API.** A background thread refreshes the adapters; `/metrics` reads the cache.
* **Dependency injection via a container** (`app/container.py`). Tests inject fake collectors, command runners and
  cloud sessions, so the suite needs no cloud account, no systemd and no root.
* **Safety is structural, not procedural.** The request schema forbids unknown fields and the action enum is the
  allowlist, so there is nowhere to pass a command. See [security.md](security.md).
* **Two views of the host.** `cloudops_*` metrics come from psutil inside the API's namespace; Node Exporter gives
  the host's own view. Inside Docker Desktop (WSL2 backend) both describe the Docker VM, not Windows itself.
