#!/bin/bash
# Scene 1: input()'s frame on dark-calc's fixed stack.
set -u
cd "$(dirname "$0")/../.." || exit 1
gdb -q -batch "$HOME/lab3/dark-calc" \
  -ex 'set pagination off' \
  -ex 'set disable-randomization off' \
  -ex 'break *input' \
  -ex 'run < /tmp/lab3-inputs/eight.bin' \
  -ex 'printf "entry       : rbp=%#lx  rsp=%#lx\n", $rbp, $rsp' \
  -ex 'nexti' -ex 'nexti' -ex 'nexti' \
  -ex 'printf "after prolog: rbp=%#lx  rsp=%#lx\n", $rbp, $rsp' \
  -ex 'printf "buffer      : rbp-0x10 = %#lx\n", $rbp-0x10' \
  -ex 'printf "saved rbp   : [rbp]    = %#lx\n", *(unsigned long*)$rbp' \
  -ex 'printf "return addr : [rbp+8]  = %#lx\n", *(unsigned long*)($rbp+8)' \
  -ex 'x/4gx $rbp-0x10'
