#!/usr/bin/env bash
set -u
cd ~/lab3 || exit 1
python3 -c "open('/tmp/l24.bin','wb').write(b'1'*24+b'\n')"
gdb -q -batch \
  -ex 'set pagination off' \
  -ex 'set disable-randomization off' \
  -ex 'run < /tmp/l24.bin' \
  -ex 'info registers rip rbp rsp' \
  -ex 'bt 4' \
  -ex 'x/4i $pc-8' \
  --args ~/lab3/dark-calc 2>&1 | tail -14
