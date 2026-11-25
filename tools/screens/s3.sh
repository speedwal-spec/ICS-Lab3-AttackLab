#!/usr/bin/env bash
# Scene 3: payload dumps only; no target program is executed.
set -Eeuo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/../.."
for p in payload.py payload_dark.py payload_rop.py payload_canary.py; do
  data=$(mktemp /tmp/attacklab-payload.XXXXXX)
  trap 'rm -f -- "$data"' EXIT
  python3 "$p" > "$data"
  n=$(wc -c < "$data")
  printf '== %s  (%s bytes incl. newline)\n' "$p" "$n"
  od -An -tx1 -v -N48 "$data"
  rm -f -- "$data"
  trap - EXIT
done
