#!/usr/bin/env python3
"""Content validation of the built DOCX: all seven task sections present, the
appendix C hash table matches the files on disk, and no stale stub hashes."""
import hashlib
import json
import os
import sys

from docx import Document

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCX = os.path.join(ROOT, "analysis", "Lab3-AttackLab-实验报告.docx")

doc = Document(DOCX)
paras = [p.text for p in doc.paragraphs]
rows = [cell.text for t in doc.tables for row in t.rows for cell in row.cells]
full = "\n".join(paras) + "\n" + "\n".join(rows)

required = [
    "观察 input 栈帧",
    "不同长度字符串输入测试",
    "利用缓冲区漏洞执行 ./malware",
    "用 GDB 检查 main 函数的机器码",
    "栈空间执行",
    "ROP",
    "Canary",
    "0x401a6b",
    "0x721000800fd0",
    "Hope A will be your grade!",
    "You have successfully detonated the bomb! Congratulations!",
    "stack smashing detected",
]
print("== required sections/markers ==")
ok = True
for needle in required:
    hit = needle in full
    print(f"{needle:60s} -> {hit}")
    ok = ok and hit

baseline = json.load(open(os.path.join(ROOT, "analysis", "baseline.json"),
                          encoding="utf-8"))
print("== appendix C hash freshness ==")
for rel in ("payload.py", "payload_dark.py", "payload_rop.py", "payload_canary.py"):
    h = baseline["files"][rel]["sha256"]
    disk = hashlib.sha256(open(os.path.join(ROOT, rel), "rb").read()).hexdigest()
    hit = h in full
    print(f"{rel:20s} {h[:16]}…  quoted={hit}  matches-disk={h == disk}")
    ok = ok and hit and (h == disk)

print("== stale stub hashes must be absent ==")
for h in ("5b0f22e7f05f8dbb", "a010b183ffe884a5",
          "194c52e630495a4f", "79e4f9431032d90f"):
    hit = h in full
    print(f"{h}  present={hit}")
    ok = ok and not hit

print("paragraphs:", len(paras), " tables:", len(doc.tables))
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
