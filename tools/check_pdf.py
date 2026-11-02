#!/usr/bin/env python3
"""Structural validation of the exported PDF: pages, fonts, text content, and
hash-table freshness (appendix C must quote the hashes of the files on disk)."""
import json
import os
import re
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(ROOT, "Lab3-AttackLab-实验报告.pdf")
raw = open(PDF, "rb").read()
print("size:", len(raw))
print("signature:", raw[:5])

blob = raw
for _ in range(4):  # unpack nested object streams
    parts = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", blob, re.S):
        data = m.group(1)
        try:
            data = zlib.decompress(data)
        except Exception:
            pass
        parts.append(data)
    blob = b"\n".join(parts)

m = re.search(rb"/Type\s*/Pages[^>]*?/Count\s+(\d+)", raw)
print("page-tree /Count:", int(m.group(1)) if m else None)
outline = sorted(set(int(x) for x in re.findall(rb"/Count\s+(\d+)", raw)))
print("outline-node /Count values (bookmarks):", outline)

markers = [
    ("实验报告", "实验报告"),
    ("AttackLab", "AttackLab"),
    ("0x401a6b", "0x401a6b"),
    ("0x721000800fd0", "0x721000800fd0"),
    ("successfully detonated", "successfully detonated"),
    ("stack smashing", "stack smashing"),
    ("Hope A will be your grade", "Hope A will be your grade"),
    ("grade_eval", "grade_eval"),
    ("ROP", "ROP"),
    ("Canary", "Canary"),
]
for label, needle in markers:
    encodings = [needle.encode("utf-8"),
                 needle.encode("utf-16-be")]
    hit = any(enc in blob for enc in encodings) or any(enc in raw for enc in encodings)
    print(f"{label:28s} -> {hit}")

print("-- appendix hash freshness (vs analysis/baseline.json) --")
baseline = json.load(open(os.path.join(ROOT, "analysis", "baseline.json"),
                          encoding="utf-8"))
for rel in ("payload.py", "payload_dark.py", "payload_rop.py", "payload_canary.py"):
    h = baseline["files"][rel]["sha256"]
    hit = h.encode() in blob or h.encode() in raw
    print(f"{rel:20s} sha256 quoted -> {hit}")

fonts = sorted(set(re.findall(rb"/BaseFont\s*/([A-Za-z0-9+#\-]+)", blob)))
print("fonts:", [f.decode("ascii", "replace") for f in fonts])
