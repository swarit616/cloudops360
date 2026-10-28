#!/usr/bin/env bash
# One-command local setup for Ubuntu / WSL2: virtualenv, dependencies and .env.
# Usage: scripts/setup.sh
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

say() { printf '==> %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }

# --- Environment checks ---------------------------------------------------------------
if grep -qi microsoft /proc/version 2>/dev/null; then
  say "WSL detected"
  case "$PWD" in
    /mnt/[a-z]/*) warn "Project is on the Windows drive ($PWD). Move it into the Linux filesystem (e.g. ~/projects) for speed and correct file permissions." ;;
  esac
fi

command -v python3 >/dev/null 2>&1 || { echo "python3 not found: sudo apt install python3 python3-venv python3-pip" >&2; exit 1; }
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "Python 3.11+ is required (found $(python3 --version))" >&2
  exit 1
fi
python3 -c 'import venv, ensurepip' 2>/dev/null || { echo "python3-venv missing: sudo apt install python3-venv" >&2; exit 1; }

# --- Python environment ---------------------------------------------------------------
if [ ! -d .venv ]; then
  say "Creating virtual environment (.venv)"
  python3 -m venv .venv
fi
say "Installing dependencies"
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements-dev.txt

# --- Configuration --------------------------------------------------------------------
if [ ! -f .env ]; then
  cp .env.example .env
  say "Created .env from .env.example (edit it; it is git-ignored)"
fi

# --- Optional tooling -----------------------------------------------------------------
for tool in docker terraform make; do
  if command -v "$tool" >/dev/null 2>&1; then
    say "$tool: found"
  else
    warn "$tool not found (optional; see docs/setup.md)"
  fi
done
if command -v docker >/dev/null 2>&1 && ! docker info >/dev/null 2>&1; then
  warn "Docker is installed but not reachable. Start Docker Desktop and enable WSL integration for this distro."
fi

chmod +x scripts/*.sh
say "Done. Next: 'make test' then 'make run' (or 'make docker-up')."
