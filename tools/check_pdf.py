#!/usr/bin/env python3
"""QA for the delivered report pair.

PDF checks are structural (signature, page tree, EOF, embedded fonts, images);
content checks run against the DOCX, which is the source of truth for what the
PDF renders (LibreOffice stores text as glyph IDs + ToUnicode maps, so raw
byte-search of the PDF cannot verify content).
"""
import hashlib
import os
import re
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(ROOT, "Lab3-AttackLab-实验报告.pdf")
DOCX = os.path.join(ROOT, "Lab3-AttackLab-实验报告.docx")

raw = open(PDF, "rb").read()
print("== PDF structural ==")
print("size:", len(raw))
print("signature:", raw[:5])
m = re.search(rb"/Type\s*/Pages[^>]*?/Count\s+(\d+)", raw)
print("page-tree /Count:", int(m.group(1)) if m else None)
print("has %%EOF:", b"%%EOF" in raw[-64:])
print("ToUnicode maps:", len(re.findall(rb"/ToUnicode", raw)))
print("image xobjects:", len(re.findall(rb"/Subtype\s*/Image", raw)))
fonts = sorted(set(re.findall(rb"/BaseFont\s*/([A-Za-z0-9+#\-]+)", raw)))
print("embedded fonts:", [f.decode("ascii", "replace") for f in fonts])

print("\n== DOCX content ==")
with zipfile.ZipFile(DOCX) as z:
    text = z.read("word/document.xml").decode("utf-8", "replace")
markers = ["实验报告", "AttackLab", "0x401a6b", "0x721000800fd0",
           "successfully detonated", "stack smashing",
           "Hope A will be your grade", "grade_eval", "推理手记", "48 字节"]
for needle in markers:
    print(f"{needle:28s} -> {needle in text}")

print("\n== payload hash freshness (appendix C vs files on disk) ==")
for name in ("payload.py", "payload_dark.py", "payload_rop.py", "payload_canary.py"):
    h = hashlib.sha256(open(os.path.join(ROOT, name), "rb").read()).hexdigest()
    print(f"{name:20s} {h} quoted -> {h in text}")
