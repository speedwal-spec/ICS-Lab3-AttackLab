#!/usr/bin/env bash
# Regenerate static disassembly of the three ELF targets into analysis/disassembly/.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p analysis/disassembly
for bin in dark-calc dark-calc-nx dark-log; do
  objdump -d -M intel "attack/$bin" > "analysis/disassembly/$bin.txt"
  echo "wrote analysis/disassembly/$bin.txt ($(wc -l < "analysis/disassembly/$bin.txt") lines)"
done
