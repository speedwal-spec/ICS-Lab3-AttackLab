#!/bin/bash
# Scene 4: dark-log -- canary untouched, return address rewritten by the memcpy.
set -u
cd "$(dirname "$0")/../.." || exit 1
python3 payload_canary.py > /tmp/lab3-inputs/canary.bin
gdb -q -batch -x tools/gdb/04_canary.gdb 2>&1 | sed -n '1,36p'
