#!/usr/bin/env bash
# Read-only disk report: filesystems over a threshold plus the largest directories.
# Usage: scripts/disk_check.sh [threshold_percent=85] [path=/]
set -euo pipefail

THRESHOLD="${1:-85}"
TARGET="${2:-/}"

case "$THRESHOLD" in
  '' | *[!0-9]*) echo "threshold must be an integer percentage" >&2; exit 2 ;;
esac
[ -d "$TARGET" ] || { echo "not a directory: $TARGET" >&2; exit 2; }

echo "== Filesystem usage (threshold ${THRESHOLD}%) =="
# -P: POSIX output (one line per fs). Exclude pseudo and Windows-mounted (9p) filesystems for WSL.
alerts=0
while read -r _fs _size _used _avail pct mount; do
  value="${pct%\%}"
  if [ "$value" -ge "$THRESHOLD" ]; then
    echo "ALERT ${mount} is ${pct} full"
    alerts=$((alerts + 1))
  else
    echo "ok    ${mount} ${pct}"
  fi
done < <(df -P -x tmpfs -x devtmpfs -x squashfs -x overlay -x 9p 2>/dev/null | tail -n +2)

echo
echo "== Largest directories under ${TARGET} (single filesystem, top 10) =="
du -xh --max-depth=1 "$TARGET" 2>/dev/null | sort -rh | head -n 10 || true

echo
echo "== Largest files in /tmp/cloudops360 (cleanup directory) =="
if [ -d /tmp/cloudops360 ]; then
  find /tmp/cloudops360 -xdev -type f -printf '%s\t%p\n' 2>/dev/null | sort -rn | head -n 10 || true
else
  echo "(directory does not exist)"
fi

[ "$alerts" -eq 0 ] || exit 1
