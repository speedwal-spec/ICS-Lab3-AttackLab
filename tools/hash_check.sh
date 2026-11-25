#!/usr/bin/env bash
# Verify attack/ against the official CI checksums and publish one fresh log.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

log="analysis/logs/hash_check.txt"
mkdir -p analysis/logs || exit 1
tmp="$(mktemp "$log.tmp.XXXXXX")" || exit 1
trap 'rm -f -- "$tmp"' EXIT HUP INT TERM

status=0
{
  echo "# sha256sum check of attack/ against .github/workflows/lab3-checks.yml"
  sha256sum --check --strict - <<'EOF' || status=$?
a9c3d4a5eed6a937e85884f6a53faa39613d49e04792e2c411620fcc74f79097  attack/dark-calc
86c2c8dfaf4a89eb7a1396d9731bfb7ee085f0b45c86687b41547a30b5b1c613  attack/dark-calc-nx
9a4479f2a522d377055b54d328d5c0e0f3ca1327708ac792028ec03cadaee31d  attack/dark-log
03289add49f13e8573d125c8949bd88c9892e84f205802613a6baa2318fb18bc  attack/malware
EOF
  echo "exit=$status"
  echo
  echo "# payload scripts (LF) and report files"
  ls -l payload.py payload_dark.py payload_rop.py payload_canary.py || status=$?
  echo "RESULT: $([ "$status" -eq 0 ] && echo PASS || echo FAIL)"
  :
} > "$tmp" 2>&1
write_status=$?
if [ "$write_status" -ne 0 ]; then
  echo "failed to write temporary hash log" >&2
  exit "$write_status"
fi
mv -f -- "$tmp" "$log" || exit 1
trap - EXIT HUP INT TERM
cat -- "$log" || exit 1
exit "$status"
