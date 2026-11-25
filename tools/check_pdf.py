#!/usr/bin/env python3
"""Fail-closed structural checks for the PDF and source hashes in the DOCX.

The standard-library structural checks do not pretend to extract PDF text. If
pypdf is installed, decoded page text is also checked for required markers.
Missing pypdf is an explicit SKIP for that extra content check, not a false
claim that PDF text was extracted. The DOCX checker separately covers content.
"""
import hashlib
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "Lab3-AttackLab-实验报告.pdf"
DOCX = ROOT / "Lab3-AttackLab-实验报告.docx"
MARKERS = (
    "实验报告", "AttackLab", "0x401a6b", "0x721000800fd0",
    "successfully detonated", "stack smashing",
    "Hope A will be your grade", "grade_eval", "推理手记", "48 字节",
)
SOURCES = ("attacklab.py", "payload.py", "payload_dark.py",
           "payload_rop.py", "payload_canary.py")


def main():
    ok = True
    raw = PDF.read_bytes()
    print("== PDF structural ==")
    print("size:", len(raw))
    print("signature:", raw[:8])
    match = re.search(rb"/Type\s*/Pages\b[^>]*?/Count\s+(\d+)", raw, re.DOTALL)
    page_count = int(match.group(1)) if match else 0
    to_unicode = len(re.findall(rb"/ToUnicode\b", raw))
    images = len(re.findall(rb"/Subtype\s*/Image\b", raw))
    fonts = sorted(set(re.findall(rb"/BaseFont\s*/([A-Za-z0-9+#\-]+)", raw)))
    embedded_fonts = len(re.findall(rb"/FontFile(?:2|3)?\b", raw))
    structural = (
        ("PDF signature and version", re.match(rb"%PDF-[0-9]+\.[0-9]+", raw) is not None),
        ("positive page-tree count", page_count > 0),
        ("document catalog", re.search(rb"/Type\s*/Catalog\b", raw) is not None),
        ("startxref", re.search(rb"startxref\s+[0-9]+", raw[-2048:]) is not None),
        ("EOF near end", b"%%EOF" in raw[-1024:]),
        ("Unicode font mappings", to_unicode > 0),
        ("embedded fonts", bool(fonts) and embedded_fonts > 0),
        ("report images", images > 0),
    )
    for label, passed in structural:
        print(f"{label:32s} -> {'PASS' if passed else 'FAIL'}")
        ok = ok and passed
    print("page-tree /Count:", page_count or None)
    print("ToUnicode maps:", to_unicode)
    print("image xobjects:", images)
    print("font resources:", [font.decode("ascii", "replace") for font in fonts])
    print("embedded font streams:", embedded_fonts)

    print("\n== decoded PDF text (optional pypdf check) ==")
    try:
        from pypdf import PdfReader
    except ImportError:
        print("SKIP: install requirements-tools.txt to verify PDF body text; "
              "structural checks above do not prove text content.")
    else:
        reader = PdfReader(str(PDF))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        print("pages:", len(reader.pages), "decoded text characters:", len(text))
        if not text:
            ok = False
        for marker in MARKERS:
            passed = marker in text
            print(f"{marker:28s} -> {'PASS' if passed else 'FAIL'}")
            ok = ok and passed

    print("\n== DOCX appendix source-hash freshness ==")
    with zipfile.ZipFile(DOCX) as archive:
        xml = archive.read("word/document.xml").decode("utf-8", "replace")
    for name in SOURCES:
        digest = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        passed = digest in xml
        print(f"{name:20s} {digest} quoted -> {'PASS' if passed else 'FAIL'}")
        ok = ok and passed

    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        print(f"check_pdf: {exc}", file=sys.stderr)
        sys.exit(1)
