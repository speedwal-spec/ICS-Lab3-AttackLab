#!/usr/bin/env bash
# Isolated local reproduction of the official payload checks (Linux x86-64).
set -uo pipefail
ulimit -c 0 || exit 1

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || exit 1
cd "$root" || exit 1
workdir="$(mktemp -d)" || exit 1
if [ -z "$workdir" ] || [ ! -d "$workdir" ]; then
  echo "could not create a temporary directory" >&2
  exit 1
fi
trap 'rm -rf -- "$workdir"' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

# Verify the repository assets before copying them into the executable sandbox.
sha256sum --check --strict - <<'EOF' || exit 1
a9c3d4a5eed6a937e85884f6a53faa39613d49e04792e2c411620fcc74f79097  attack/dark-calc
86c2c8dfaf4a89eb7a1396d9731bfb7ee085f0b45c86687b41547a30b5b1c613  attack/dark-calc-nx
9a4479f2a522d377055b54d328d5c0e0f3ca1327708ac792028ec03cadaee31d  attack/dark-log
03289add49f13e8573d125c8949bd88c9892e84f205802613a6baa2318fb18bc  attack/malware
EOF

mkdir -p "$workdir/bin" || exit 1
for name in dark-calc dark-calc-nx dark-log malware; do
  cp "attack/$name" "$workdir/bin/$name" || exit 1
  chmod +x "$workdir/bin/$name" || exit 1
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
  if [ ! -f "$payload" ]; then
    echo "   FAIL: missing generator $payload"
    failed=1
    continue
  fi

  gen_status=0
  timeout 15s python3 "$payload" > "$workdir/payload.bin" \
    2> "$workdir/generate.err" || gen_status=$?
  if [ "$gen_status" -ne 0 ]; then
    echo "   FAIL: generator failed or timed out (exit $gen_status)"
    sed -n 1,20p "$workdir/generate.err" || failed=1
    failed=1
    continue
  fi
  if [ ! -s "$workdir/payload.bin" ]; then
    echo "   FAIL: generator wrote no bytes"
    failed=1
    continue
  fi

  status=0
  ( cd "$workdir/bin" && timeout 15s "./$target" < "$workdir/payload.bin" \
      > "$workdir/stdout.txt" 2> "$workdir/stderr.txt" ) || status=$?

  echo "   payload bytes: $(wc -c < "$workdir/payload.bin")   target exit: $status"
  # Match official CI: stdout is decisive; an original target crash is recorded
  # in target exit but is not an additional failure condition.
  if grep -Fq -- "$expected" "$workdir/stdout.txt"; then
    echo "   PASS"
  else
    echo "   FAIL: expected '$expected' in stdout (target exit $status)"
    failed=1
  fi
  sed -n 1,10p "$workdir/stdout.txt" | cat -v || failed=1
  if [ -s "$workdir/stderr.txt" ]; then
    echo "   --- stderr ---"
    sed -n 1,10p "$workdir/stderr.txt" | cat -v || failed=1
  fi
done

if [ "$failed" -ne 0 ]; then
  echo "RESULT: FAIL"
  exit 1
fi
echo "RESULT: PASS (4/4)"
