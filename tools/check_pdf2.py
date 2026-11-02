#!/usr/bin/env python3
"""Final PDF sanity: page count, EOF marker, xref presence."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(ROOT, "Lab3-AttackLab-实验报告.pdf")
raw = open(PDF, "rb").read()
m = re.search(rb"/Type\s*/Pages[^>]*?/Count\s+(\d+)", raw)
print("page-tree /Count (total pages):", int(m.group(1)) if m else None)
print("has %%EOF:", b"%%EOF" in raw[-64:])
print("xref objects:", len(re.findall(rb"^\d+\s+\d+\s+obj", raw, re.M)))
print("image xobjects:", len(re.findall(rb"/Subtype\s*/Image", raw)))
