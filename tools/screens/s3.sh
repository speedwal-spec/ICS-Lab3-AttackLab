#!/bin/bash
# Scene 3: byte layout of the four payloads, as they are fed on stdin.
set -u
cd "$(dirname "$0")/../.." || exit 1
for p in payload.py payload_dark.py payload_rop.py payload_canary.py; do
  n=$(python3 "$p" | wc -c)
  echo "== $p  ($n bytes incl. newline)"
  python3 "$p" | od -An -tx1 -v | head -3
done
