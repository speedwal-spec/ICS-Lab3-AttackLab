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
import os
import subprocess
import sys
import tempfile

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


def disasm(path, file_off, vaddr, count=20):
    """Disassemble `count` bytes at file offset `file_off`, labelled at `vaddr`.

    objdump -b binary maps the file at 0, so feeding it the whole ELF would
    disassemble the file header; slice the bytes first and shift the VMA.
    """
    with open(path, "rb") as fh:
        fh.seek(file_off)
        code = fh.read(count)
    fd, tmp = tempfile.mkstemp(suffix=".bin")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(code)
        proc = subprocess.run(
            ["objdump", "-D", "-b", "binary", "-m", "i386:x86-64", "-M", "intel",
             f"--adjust-vma=0x{vaddr:x}", tmp],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"objdump failed for {path} at file offset 0x{file_off:x} "
                               f"(rc={proc.returncode}):\n{proc.stderr.strip()}")
        out = proc.stdout
    finally:
        os.unlink(tmp)
    return "\n".join(ln for ln in out.splitlines() if re.match(r"^\s*[0-9a-f]+:", ln))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("binary")
    ap.add_argument("patterns", nargs="+", help="hex byte patterns, e.g. 5fc3")
    ap.add_argument("--window", type=int, default=24,
                    help="bytes to disassemble after each match (positive)")
    args = ap.parse_args()
    if args.window <= 0:
        ap.error("--window must be positive")

    data, segs = load_segments(args.binary)
    for pat in args.patterns:
        try:
            needle = bytes.fromhex(pat)
        except ValueError as exc:
            ap.error(f"invalid hex pattern {pat!r}: {exc}")
        if not needle:
            ap.error("hex patterns must contain at least one byte")
        hits = [m.start() for m in re.finditer(re.escape(needle), data)]
        print(f"== {pat} ({len(hits)} hits) in {args.binary}")
        for off in hits:
            v = vaddr_of(segs, off)
            print(f"  file=0x{off:x} vaddr=0x{v:x}" if v is not None else f"  file=0x{off:x} vaddr=<not exec>")
            if v is not None:
                print("    " + disasm(args.binary, off, v, args.window).replace("\n", "\n    "))


if __name__ == "__main__":
    sys.exit(main())
