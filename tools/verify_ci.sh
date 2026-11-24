#!/usr/bin/env bash
# Local reproduction of .github/workflows/lab3-checks.yml "Test each payload".
# Usage: bash tools/verify_ci.sh      (run from the repository root, on Linux x86-64)
set -u

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root" || exit 1

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

# The lab binaries live on a shared folder where the exec bit may not survive.
mkdir -p "$workdir/bin"
for name in dark-calc dark-calc-nx dark-log malware; do
  cp "attack/$name" "$workdir/bin/$name" || { echo "missing attack/$name"; exit 1; }
  chmod +x "$workdir/bin/$name"
done

cases=(
  "payload.py|dark-calc|You have successfully detonated the bomb! Congratulations!"
  "payload_dark.py|dark-calc|Hope A will be your grade!"
  "payload_rop.py|dark-calc-nx|Hope A will be your grade!"
  "payload_canary.py|dark-log|Hope A will be your grade!"
)

failed=0
for case in "${cases[@]}"; do
  IFS='|' read -r payload target expected <<< "$case"
  echo "== $payload -> attack/$target"

  if ! python3 "$payload" > "$workdir/payload.bin" 2> "$workdir/generate.err"; then
    echo "   FAIL: generator failed"; sed -n 1,20p "$workdir/generate.err"; failed=1; continue
  fi
  if [ ! -s "$workdir/payload.bin" ]; then
    echo "   FAIL: generator wrote no bytes"; failed=1; continue
  fi

  status=0
  ( cd "$workdir/bin" && timeout 15s "./$target" < "$workdir/payload.bin" \
      > "$workdir/stdout.txt" 2> "$workdir/stderr.txt" ) || status=$?

  echo "   payload bytes: $(wc -c < "$workdir/payload.bin")   target exit: $status"
  if grep -Fq -- "$expected" "$workdir/stdout.txt"; then
    echo "   PASS"
  else
    echo "   FAIL: expected '$expected'"
    failed=1
  fi
  sed -n 1,10p "$workdir/stdout.txt" | cat -v
  if [ -s "$workdir/stderr.txt" ]; then
    echo "   --- stderr ---"; sed -n 1,10p "$workdir/stderr.txt" | cat -v
  fi
done

if [ "$failed" -ne 0 ]; then echo "RESULT: FAIL"; exit 1; fi
echo "RESULT: PASS (4/4)"
