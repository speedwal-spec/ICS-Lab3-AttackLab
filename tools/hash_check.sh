#!/usr/bin/env bash
# Verify that attack/ files still match the CI-recorded checksums.
set -u
cd /mnt/e/AttackLab || exit 1
{
  echo "# sha256sum check of attack/ against .github/workflows/lab3-checks.yml"
  sha256sum --check --strict - <<'EOF'
a9c3d4a5eed6a937e85884f6a53faa39613d49e04792e2c411620fcc74f79097  attack/dark-calc
86c2c8dfaf4a89eb7a1396d9731bfb7ee085f0b45c86687b41547a30b5b1c613  attack/dark-calc-nx
9a4479f2a522d377055b54d328d5c0e0f3ca1327708ac792028ec03cadaee31d  attack/dark-log
03289add49f13e8573d125c8949bd88c9892e84f205802613a6baa2318fb18bc  attack/malware
EOF
  echo "exit=$?"
  echo
  echo "# payload scripts (LF) and report files"
  ls -l payload.py payload_dark.py payload_rop.py payload_canary.py
} > analysis/logs/hash_check.txt 2>&1
cat analysis/logs/hash_check.txt
