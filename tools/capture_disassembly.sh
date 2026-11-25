#!/usr/bin/env bash
# Regenerate disassembly atomically; a failed/empty capture leaves no evidence.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
mkdir -p analysis/disassembly
tmp=''

for bin in dark-calc dark-calc-nx dark-log; do
  out="analysis/disassembly/$bin.txt"
  tmp="$(mktemp "$out.tmp.XXXXXX")"
  trap 'rm -f -- "$tmp"' EXIT
  trap 'exit 129' HUP
  trap 'exit 130' INT
  trap 'exit 143' TERM
  status=0
  objdump -d -M intel "attack/$bin" > "$tmp" 2>&1 || status=$?
  if [ "$status" -ne 0 ]; then
    rm -f -- "$tmp" "$out"
    echo "objdump failed for attack/$bin (exit $status)" >&2
    exit "$status"
  fi
  if [ ! -s "$tmp" ]; then
    rm -f -- "$tmp" "$out"
    echo "objdump produced no evidence for attack/$bin" >&2
    exit 1
  fi
  mv -f -- "$tmp" "$out"
  trap - EXIT HUP INT TERM
  echo "wrote $out ($(wc -l < "$out") lines)"
done
