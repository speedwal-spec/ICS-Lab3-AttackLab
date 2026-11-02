#!/usr/bin/env python3
"""Tiny gadget/byte-pattern scanner for the lab ELF binaries.

Uses only the Python standard library plus the system objdump: no pip packages.
It maps file offsets to virtual addresses through the PT_LOAD program headers and
prints a short disassembly window around every match so unaligned gadgets can be
confirmed by eye.
"""
import argparse
import re
import struct
import subprocess
import sys

PT_LOAD = 1


def load_segments(path):
    data = open(path, "rb").read()
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        raise SystemExit(f"{path}: not a little-endian ELF64 file")
    e_phoff = struct.unpack_from("<Q", data, 0x20)[0]
    e_phentsize = struct.unpack_from("<H", data, 0x36)[0]
    e_phnum = struct.unpack_from("<H", data, 0x38)[0]
    segs = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type, p_flags = struct.unpack_from("<II", data, off)
        p_offset, p_vaddr, _paddr, p_filesz = struct.unpack_from("<QQQQ", data, off + 8)
        if p_type == PT_LOAD and p_flags & 1:  # PF_X
            segs.append((p_offset, p_vaddr, p_filesz))
    return data, segs


def vaddr_of(segs, file_off):
    for p_offset, p_vaddr, p_filesz in segs:
        if p_offset <= file_off < p_offset + p_filesz:
            return p_vaddr + (file_off - p_offset)
    return None


def disasm(path, start, count=20):
    out = subprocess.run(
        ["objdump", "-D", "-b", "binary", "-m", "i386:x86-64", "-M", "intel",
         f"--adjust-vma=0x{start:x}", f"--start-address=0x{start:x}",
         f"--stop-address=0x{start + count:x}", path],
        capture_output=True, text=True,
    ).stdout
    return "\n".join(out.splitlines()[7:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("binary")
    ap.add_argument("patterns", nargs="+", help="hex byte patterns, e.g. 5fc3")
    ap.add_argument("--window", type=int, default=24)
    args = ap.parse_args()

    data, segs = load_segments(args.binary)
    for pat in args.patterns:
        needle = bytes.fromhex(pat)
        hits = [m.start() for m in re.finditer(re.escape(needle), data)]
        print(f"== {pat} ({len(hits)} hits) in {args.binary}")
        for off in hits:
            v = vaddr_of(segs, off)
            print(f"  file=0x{off:x} vaddr=0x{v:x}" if v is not None else f"  file=0x{off:x} vaddr=<not exec>")
            if v is not None:
                print("    " + disasm(args.binary, v, args.window).replace("\n", "\n    "))


if __name__ == "__main__":
    sys.exit(main())
