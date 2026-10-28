#!/usr/bin/env bash
# Checks that the CloudOps360 stack is reachable. Exit code 0 = all checks passed.
# Override targets with API_URL, PROMETHEUS_URL, GRAFANA_URL.
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:8000}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://127.0.0.1:9090}"
GRAFANA_URL="${GRAFANA_URL:-http://127.0.0.1:3000}"

failures=0

check() {
  local name="$1" url="$2"
  if curl -fsS --max-time 5 -o /dev/null "$url"; then
    printf 'OK    %-22s %s\n' "$name" "$url"
  else
    printf 'FAIL  %-22s %s\n' "$name" "$url" >&2
    failures=$((failures + 1))
  fi
}

command -v curl >/dev/null 2>&1 || { echo "curl is required" >&2; exit 2; }

check "CloudOps360 /health" "${API_URL}/health"
check "CloudOps360 /metrics" "${API_URL}/metrics"
check "Prometheus ready" "${PROMETHEUS_URL}/-/ready"
check "Grafana health" "${GRAFANA_URL}/api/health"

if curl -fsS --max-time 5 "${PROMETHEUS_URL}/api/v1/targets" 2>/dev/null | grep -q '"health":"down"'; then
  echo "WARN  at least one Prometheus target is DOWN (see ${PROMETHEUS_URL}/targets)" >&2
  failures=$((failures + 1))
fi

if [ "$failures" -gt 0 ]; then
  echo "${failures} check(s) failed" >&2
  exit 1
fi
echo "All checks passed"
