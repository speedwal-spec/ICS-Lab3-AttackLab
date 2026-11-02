#!/usr/bin/env bash
# Probe how the system shell parses arithmetic expansion with command substitution.
cd ~/lab3 || exit 1
echo "--- /bin/sh -> $(readlink -f /bin/sh)"
for shell in dash bash; do
  echo "=== $shell ==="
  $shell -c 'echo $(( $(echo 42) ))' 2>&1
  echo "status=$?"
  $shell -c 'echo $(($(./malware)))' 2>&1 | head -20
  echo "status=$?"
done
