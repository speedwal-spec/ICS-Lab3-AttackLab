#!/bin/bash
# Scene 2: the fixed mmap'd stack, rwxp between two PROT_NONE guard pages.
set -u
cd "$(dirname "$0")/../.." || exit 1
gdb -q -batch "$HOME/lab3/dark-calc" \
  -ex 'set pagination off' \
  -ex 'set disable-randomization off' \
  -ex 'break main' \
  -ex 'run < /tmp/lab3-inputs/eight.bin' \
  -ex 'printf "at main(): rsp=%#lx\n", $rsp' \
  -ex 'info proc mappings' 2>&1 | sed -n '1,18p'
