#!/usr/bin/env bash
# Scene 2: the fixed mmap'd stack, rwxp between two PROT_NONE guard pages.
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
attacklab_prepare
printf '1\n' > "$ATTACKLAB_FIXTURE_DIR/eight.bin"
gdb -q -nx -batch "$ATTACKLAB_WORKDIR/dark-calc" \
  -ex 'set pagination off' \
  -ex 'set disable-randomization off' \
  -ex 'break main' \
  -ex "run < $ATTACKLAB_FIXTURE_DIR/eight.bin" \
  -ex 'printf "at main(): rsp=%#lx\n", $rsp' \
  -ex 'info proc mappings' 2>&1 | sed -n '1,18p'
