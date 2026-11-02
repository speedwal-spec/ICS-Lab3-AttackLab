#!/usr/bin/env bash
# Confirm the unaligned pop-rdi-ret gadgets and the surrounding epilogues.
set -u
cd ~/lab3 || exit 1
show() {
  local bin=$1 start=$2
  echo "=== $bin @ 0x$start ==="
  objdump -d -M intel --start-address=0x$start --stop-address=$((0x$start + 8)) "$bin" |
    awk '/^ +[0-9a-f]+:/'
}
show dark-calc 401c92
show dark-calc-nx 401a32
show dark-log 4018a2
