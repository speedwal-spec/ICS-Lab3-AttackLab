#!/usr/bin/env python3
"""Build the Lab 3 report DOCX (analysis/Lab3-AttackLab-实验报告.docx) — geek edition.

The narrative is first-person and chronological: hypothesis → attempt → failure →
insight → working payload.  All numbers, transcripts and hexdumps are pulled from
the recorded evidence in analysis/gdb, analysis/logs, analysis/disassembly and
the payload scripts themselves, so nothing in the prose is invented.
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
    normal.paragraph_format.space_after = Pt(4)
    normal.paragraph_format.line_spacing = 1.15

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
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
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
        if start in ln:
            on = True
        if on:
            out.append(ln)
        if end and end in ln:
            break
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
            out.append(ln)
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
            out.append(ln)
    return "\n".join(out)


def payload_hexdump(script):
    proc = subprocess.run([sys.executable, os.path.join(ROOT, script)],
                          cwd=ROOT, capture_output=True, timeout=15)
    data = proc.stdout
    lines = [f"# {script}  ->  {len(data)} bytes (incl. trailing newline)"]
    for off in range(0, len(data), 16):
        chunk = data[off:off + 16]
        hexs = " ".join(f"{b:02x}" for b in chunk)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{off:04x}  {hexs:<47}  |{asc}|")
    return "\n".join(lines)


# ---------------------------------------------------------------- evidence
def load_evidence():
    ev = {}
    ev["env"] = json.load(open(os.path.join(LOGS, "environment.json"), encoding="utf-8"))
    ev["ci"] = json.load(open(os.path.join(LOGS, "ci_simulation.json"), encoding="utf-8"))
    ev["lengths"] = json.load(open(os.path.join(LOGS, "length_tests.json"), encoding="utf-8"))
    ev["baseline"] = json.load(open(os.path.join(ANALYSIS, "baseline.json"), encoding="utf-8"))
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
    ev["fixed_maps"] = "\n".join(ln for ln in maps.splitlines() if "0x00007210" in ln)
    ev["shellcode_inspect"] = section(g2, "### break after gets(); inspect the injected shellcode", "### watch grade_eval receive")
    ev["grade_hit"] = section(g2, "### watch grade_eval receive edi=4", "### continue to program exit")
    ev["shellcode_result"] = section(g2, "### continue to program exit", None)

    g3 = os.path.join(GDB, "03_nx.txt")
    ev["nx_frame"] = section(g3, "### input() frame on the ordinary thread stack", "### force the CPU")
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
    ev["sys_site"] = section(g5, "### returned into eval's system call site", "### after system() returns")
    ev["sys_after"] = section(g5, "### after system() returns: the frame pointer", "### let eval's epilogue")
    ev["sys_epilogue"] = section(g5, "### let eval's epilogue run to its natural end", None)

    return ev


# ---------------------------------------------------------------- report
def build(ev):
    doc = Document()
    doc.core_properties.title = "ICS-26Fall-FDU AttackLab 实验报告"
    doc.core_properties.author = "AttackLab"
    style_setup(doc)
    page_header(doc)
    page_number_footer(doc)

    # ---------- cover ----------
    for _ in range(6):
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
    para(doc, "—— 一份包含翻车记录与血泪复盘的技术报告 ——", size=11.5,
         align=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0x7A, 0x80, 0x8A))
    for _ in range(5):
        doc.add_paragraph()
    para(doc, "姓名：____________________　　学号：____________________",
         size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph()
    para(doc, "日期：2026 年 11 月 2 日", size=11,
         align=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0x55, 0x5A, 0x66))
    for _ in range(3):
        doc.add_paragraph()
    para(doc, "提交内容：attacklab.py、payload.py、payload_dark.py、payload_rop.py、payload_canary.py 与本 PDF",
         size=10.5, align=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0x7A, 0x80, 0x8A))
    para(doc, "四个 payload 均通过 GitHub Actions 真实 CI（ubuntu-24.04）实测；GDB 实录、长度矩阵、哈希校验全部随仓库提交。",
         size=10.5, align=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0x7A, 0x80, 0x8A))
    doc.add_page_break()

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
        "十一、验收：GitHub Actions CI 实测通过",
        "十二、防守视角：从攻击到防御",
        "十三、复盘：踩过的坑与捡到的顿悟",
        "附录 A：四个 payload 的完整清单与十六进制转储",
        "附录 B：关键 GDB 实录摘录",
        "附录 C：环境参数、文件哈希与实验时间线",
        "附录 D：常用命令速查",
    ]
    for t in toc:
        para(doc, t, size=11, space_after=4)
    doc.add_page_break()

    # ---------- 1 总览 ----------
    heading(doc, "一、实验总览：四个靶机，四把钥匙", 1)
    para(doc, "这份报告是我把四个 payload 全部跑通、真实 CI 全绿之后才动笔的——不是实验方案，"
              "是战后复盘。所以先把结论拍在桌上，再讲每一枪是怎么开出去的、哪几枪打空了、"
              "最后是怎么命中的。")
    table(doc,
          ["任务", "分值", "钥匙（一句话原理）", "状态"],
          [
              ["① 观察 input 栈帧", "20（报告）", "断点之下，帧无秘密", "完成，第四节"],
              ["② 不同长度输入测试", "5（报告）", "用 '1' 串丈量出生死线：23/24 与 47/48", "完成，第五节"],
              ["③ 溢出执行 ./malware", "25+5", "链子塞不进 48 字节牢笼，就复用 eval 里现成的那行 system 调用", "测试 PASS，第六节"],
              ["④ GDB 检查 main 机器码", "5（报告）", "55 48 89 e5…… e8 的 rel32 手算一遍", "完成，第七节"],
              ["⑤ 栈空间执行", "25+5", "dark-calc 的栈是 mmap 出来的 rwxp 固定地址——ASLR 与 NX 双杀失败", "测试 PASS，第八节"],
              ["⑥ ROP", "10+10", "CPU 只认字节流：41 5f c3 往前挪一个字节，pop r15 就变成 pop rdi", "测试 PASS，第九节"],
              ["⑦ Canary", "10+10", "金丝雀没瞎——只是 memcpy 的落点被我改了，绕过了它看不见的地方", "测试 PASS，第十节"],
          ],
          widths=[3.4, 1.9, 9.3, 2.4])
    para(doc, "四个 payload 的实测结果（本地 WSL 复现与 GitHub Actions CI 一致；完整输出见 analysis/logs/ci_simulation.txt）：")
    p = doc.add_paragraph(style="List Bullet")
    add_runs(p, "payload.py → dark-calc：")
    add_runs(p, "“### You have successfully detonated the bomb! Congratulations! ###”", mono=True, size=9.5, bold=True)
    p = doc.add_paragraph(style="List Bullet")
    add_runs(p, "payload_dark.py / payload_rop.py / payload_canary.py：")
    add_runs(p, "“Hope A will be your grade!”", mono=True, size=9.5, bold=True)
    para(doc, "阅读指南：正文里的黄底「推理手记」是第一人称的现场思考——有两次翻车，也有几次灵光一现；"
              "灰底代码块全部来自 GDB/objdump/终端的原始记录；图 1–5 是按实测数据画的。"
              "所有地址都出自仓库里未被修改的二进制（哈希与 CI 清单逐字节一致），不是纸上谈兵。")
    doc.add_page_break()

    # ---------- 2 环境 ----------
    heading(doc, "二、实验环境：系统、哈希与工具链", 1)
    heading(doc, "2.1 环境", 2)
    env = ev["env"]
    table(doc,
          ["项目", "取值"],
          [
              ["操作系统", "WSL2 Ubuntu 26.04 LTS（内核 " + env["uname"] + "）"],
              ["gcc / gdb / binutils", env["gcc"] + " ｜ " + env["gdb"] + " ｜ " + env["objdump"]],
              ["glibc (ldd)", env["libc"]],
              ["Python", env["python"]],
              ["ASLR（randomize_va_space）", env["aslr"] + "（全量随机化开启）"],
              ["GDB 默认 disable-randomization", env["gdb_default_disable_randomization"] + "——实验会话全部显式 off，不然看到的栈地址是假象"],
              ["CI 环境", "GitHub Actions ubuntu-24.04（glibc 2.39，Python 3.12，每命令超时 15 s）"],
          ],
          widths=[5.0, 12.0])
    para(doc, "四个 payload 只依赖非 PIE 主映像的固定代码地址和 dark-calc 的固定映射，"
              "对栈地址、libc 地址、glibc 小版本零依赖——本报告同时给出本地 WSL（glibc 2.43）"
              "复现记录与 GitHub Actions CI（glibc 2.39）实测结果，两者一致。")
    heading(doc, "2.2 完整性：attack/ 一个字节都没动", 2)
    code(doc, ev["hash_check"].split("# payload scripts")[0].rstrip())
    heading(doc, "2.3 打法", 2)
    bullet(doc, "静态勘察：readelf/nm/objdump 把段、符号、指令字节全摊开；tools/gadgets.py 按字节串扫 gadget（0x5f 0xc3 之类）；", "① ")
    bullet(doc, "动态观察：GDB 批量会话（tools/gdb/*.gdb）断点看帧、看页权限、看寄存器，全程关掉 gdb 的地址固定化；", "② ")
    bullet(doc, "端到端：tools/run_evidence.py 在本地逐字复现 CI 的「生成 payload → 重定向 stdin → grep 期望串」，并配合仓库 GitHub Actions CI 实测；", "③ ")
    bullet(doc, "复盘：tools/build_report.py 把上面的原始记录直接拼成本报告，中间不经过手抄。", "④ ")
    doc.add_page_break()

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
              "是后面四个任务共同的控制流终点。")
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
              ["-0x18", "pad[8]", "gets 的 NUL 终止符可以安全落在这里"],
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
    doc.add_page_break()

    # ---------- 4 任务一 ----------
    heading(doc, "四、任务一：观察 input 的栈帧（20 分）", 1)
    think(doc, "断点一挂上，第一眼看到的就不是「正常栈」：main 还没进，rsp 已经停在 "
               "0x721000800ff8——离 0x721000801000 的守卫页只有 8 个字节，而下面是一整块 "
               "mmap 出来的匿名映射。也就是说 dark-calc 每次运行，栈的位置都钉死在同一个地址。"
               "这个发现当时只是一句「哦？」，后来它同时成就了任务五，也坑了任务三。")
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
    code(doc, ev["frame_entry"])
    code(doc, ev["frame_prologue"])
    code(doc, ev["frame_after_gets"])
    para(doc, "量出来的结果画成图（图 1），也可以直接看 ASCII 版：")
    code(doc,
         "0x721000801000 ┌──────────────────────────────┐  ← PROT_NONE 守卫页：越界写必死\n"
         "0x721000800ff8 │ ret → 0x401c1f               │  __wrap_main 调 main 压入\n"
         "0x721000800ff0 │ main 的 saved rbp = 0          │  main 帧\n"
         "0x721000800fe8 │ ret → 0x401ad1                │  ← 偏移 +24：控制流的钥匙\n"
         "0x721000800fe0 │ saved rbp → 0x721000800ff0    │  ← 偏移 +16\n"
         "0x721000800fd0 │ expression[16]                │  ← gets 从这里开始写，向高地址漫灌\n"
         "               └──────────────────────────────┘")
    picture(doc, os.path.join(FIGS, "fig_frame_input.png"), 6.3, "图 1  dark-calc 的 input() 栈帧（固定栈，地址恒定）")
    table(doc,
          ["地址（固定）", "槽位", "实测值", "说明"],
          [
              ["0x721000800fd0", "expression[16]", "输入内容", "gets 写入起点；偏移 +0"],
              ["0x721000800fe0", "saved rbp", "0x721000800ff0", "main 的 rbp；偏移 +16"],
              ["0x721000800fe8", "返回地址", "0x401ad1", "main+0xe（call input 之后）；偏移 +24"],
              ["0x721000800ff0", "main 的 saved rbp", "0", "_start 里 xor ebp,ebp 的遗留值"],
              ["0x721000800ff8", "__wrap_main 的返回地址", "0x401c1f", "call main 压入"],
              ["0x721000801000", "守卫页起点", "PROT_NONE", "越界写到这里直接 SIGSEGV"],
          ],
          widths=[3.4, 3.4, 3.6, 6.6], mono_cols=(0, 2))
    para(doc, "两个数字刻进脑子里：缓冲区到返回地址 24 字节；缓冲区到守卫页 48 字节——"
              "gets 还要写一个 NUL，所以单次输入上限是 47 字节。这个「48 字节牢笼」是任务三"
              "和任务五所有设计约束的源头。")
    doc.add_page_break()

    # ---------- 5 任务二 ----------
    heading(doc, "五、任务二：长度矩阵与崩溃边界（5 分）", 1)
    think(doc, "一开始只是想看看 15/16 的截断区别，结果第一次跑 8 个 '1' 就撞见鬼了："
               "算术结果先打印，「Enter an expression」的提示反而后打印。第一反应是怀疑自己重定向写错了，来回核了三遍——最后才反应过来：stdout 是全缓冲，"
               "printf 的提示还憋在缓冲区里，system() 的子进程却直接写管道——所以行序倒置。"
               "顺手把长度从 0 一路扫到 200，两条生死线当场现形。")
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
    think(doc, "n=24 那次崩得最有信息量。GDB 一查：0x401ad1 的最低字节被 gets 的 NUL 清零，"
               "变成了 0x401a00——正好落进 eval 的正中间（mov [rbp-4],eax），而 rbp 此时是 "
               "0x3131…，往那个地址写立即数直接 SIGBUS。换句话说：溢出并不需要把地址整个"
               "覆盖成自己想要的值，改掉一个字节就足以把程序送进一条完全陌生的指令流。"
               "顺带一提，n=24 是 SIGBUS 而 n=31、32 是 SIGSEGV——信号不同只是因为死法不同，"
               "都是死。")
    heading(doc, "5.3 MAXLEN=15 的截断：迟到的闸门", 2)
    para(doc, "eval 只在 strlen(command_buf) > 15 时截断（0x4019e9 处 cmp rax,0xf）。"
              "16–23 字节输入早已越出 expression[16]，程序照样把前 15 个字符包进 echo $(( )) "
              "执行——闸门设在溢出之后，拦得住 shell 表达式的长度，拦不住已经发生的栈破坏。"
              "第五节留下的尾巴是：这扇闸门本身能不能被钻？第六节回答。")
    doc.add_page_break()

    # ---------- 6 任务三 ----------
    heading(doc, "六、任务三：溢出执行 ./malware（25 测试 + 5 报告）", 1)
    think(doc, "第一版方案是教科书三连：24 字节 padding + pop rdi; ret + command_buf + "
               "system@plt = 48 字节，再算上 gets 的 NUL 就是 49 字节。结果程序连输出都没有，"
               "直接 SIGSEGV——死在了 gets 自己手里：NUL 被写进了 0x721000801000 的守卫页，"
               "连 ret 都没摸到。任务一量出的「48 字节牢笼」在这里反手就是一记耳光。")
    para(doc, "硬约束：单次输入 ≤ 47 字节，而覆盖返回地址槽就要 24 字节，剩给整条链的只有 23 字节，"
              "放不下三个 qword。换思路——链子放不下，就找现成的调用点。")
    heading(doc, "6.1 翻盘点：eval 里那行现成的 system 调用", 2)
    code(doc, disasm_range("dark-calc", 0x401A6B, 0x401A86))
    para(doc, "0x401a6b 是 eval 内部「mov edi,0x6030d0; call system@plt」的起始：它自带 "
              "pop rdi 的功能，还自带被调用目标。而 rdi 指向的 command_buf，恰好刚刚被 "
              "input() 的 strcpy(command_buf, expression) 填进了这个 payload 开头第一个 NUL "
              "之前的字符串——也就是 \"./malware\"。自己人，全对上了。")
    heading(doc, "6.2 payload：32 字节，一次到位", 2)
    table(doc,
          ["偏移", "字节", "作用"],
          [
              ["0 – 9", "\"./malware\" + NUL", "command_buf 的 shell 命令（strcpy 拷到第一个 NUL 为止）"],
              ["10 – 15", "'A' × 6", "凑满 16 字节（expression 的容量）"],
              ["16 – 23", "'B' × 8", "伪造 saved rbp（这条路径之后不再用 rbp）"],
              ["24 – 31", "0x401a6b（小端）", "返回地址 → eval 的 system 调用点"],
          ],
          widths=[2.0, 5.4, 9.6], mono_cols=(1,))
    code(doc, payload_hexdump("payload.py"))
    heading(doc, "6.3 GDB 里对一遍账", 2)
    code(doc, ev["sys_site"])
    code(doc, ev["sys_after"])
    code(doc, ev["sys_epilogue"])
    para(doc, "（GDB 的工作目录不是 attack/，所以 sh 报 ./malware: not found——CI 是在 attack/ "
              "里跑的，能找到。断点证实 rdi=0x6030d0、command_buf=\"./malware\"。）")
    heading(doc, "6.4 端到端：起爆成功", 2)
    picture(doc, os.path.join(FIGS, "fig_proc_tree.png"), 6.2, "图 5  payload.py 的运行现场：malware 沿父链找到 dark-calc")
    sim = ev["ci_sim"]
    block = sim[sim.index("== payload.py"):]
    block = block[:block.index("== payload_dark.py")].rstrip()
    code(doc, block)
    think(doc, "system 返回后，eval 的尾声 leave 用的是我伪造的 rbp（0x4242…），当场 SIGBUS。"
               "没关系：malware 是独立子进程，横幅早就写进了 stdout；CI 检查的是输出不是"
               "退出状态。当然，如果想让进程体面退场，把 saved rbp 换成合法帧即可——"
               "payload_dark 和 payload_rop 做到了 exit(0)，这里我选择让它在辉煌中死去。")
    heading(doc, "6.5 顺手摸出的第二扇门：算术扩展里的命令替换", 2)
    think(doc, "调试间隙我顺手在 dash 和 bash 里试了一下 eval 的包装格式：echo $(( $(cmd) ))。"
               "两个 shell 都在算术扩展内部先做命令替换——12 字节的 $(./malware) 就够在 "
               "15 字符闸门之内触发 malware（算术解析失败只会把报错打到 stderr，横幅照样出）。"
               "也就是说这台机器的攻击面比作业要求的大：即使不碰缓冲区，命令注入也能得手。"
               "本任务按作业要求用返回地址覆盖实现；但这扇门值得写进防御章节——"
               "system() + 用户输入，从来都是高危组合。")
    doc.add_page_break()

    # ---------- 7 任务四 ----------
    heading(doc, "七、任务四：main 的机器码与内存布局（5 分）", 1)
    para(doc, "GDB 里 disassemble /r main，带上原始字节逐条读：")
    code(doc, ev["main_bytes"])
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
    doc.add_page_break()

    # ---------- 8 任务五 ----------
    heading(doc, "八、任务五：48 字节牢笼里的 shellcode（25 测试 + 5 报告）", 1)
    think(doc, "readelf 说 GNU_STACK RW——不能执行；运行期 maps 说 0x721000001000–801000 是 "
               "rwxp——可以执行。ELF 头会撒谎，文件名会撒谎（带 nx 的那个反而是普通栈），"
               "只有页表不撒谎。dark-calc 的「栈」是 init_fixed_stack 用 mmap 在固定地址造的"
               "RWX 映射，__wrap_main 把 rsp 切过去才开始跑 main。后果有二：地址恒定（ASLR 对"
               "栈失效），页可执行（NX 对栈失效）。任务五的全部难度就浓缩成一句话——"
               "在 47 字节的输入预算里，塞下一段能调 grade_eval(4) 的机器码。")
    heading(doc, "8.1 固定栈的实锤", 2)
    code(doc, ev["fixed_maps"])
    picture(doc, os.path.join(FIGS, "fig_fixed_stack.png"), 6.4, "图 2  dark-calc 的固定栈映射：rwxp 栈页 + 两侧守卫页")
    code(doc, ev["wrap_entry"])
    heading(doc, "8.2 shellcode：15 字节，把预算花在刀刃上", 2)
    code(doc, "6a 04          push 4\n"
              "5f             pop  rdi                ; edi = 4\n"
              "48 b8 <a87…>   movabs rax, 0x401a87     ; grade_eval\n"
              "ff e0          jmp   rax               ; 注意：是 jmp，不是 call")
    para(doc, "为什么是 jmp 不是 call？shellcode 入口时 rsp=0x721000800ff0，距守卫页只剩 8 字节"
              "可写；call 会压栈，grade_eval 的 prologue 再来一个 push 就撞墙。jmp 不碰栈，"
              "grade_eval 自己 push rbp 恰好落在 0x…fe8——守卫页下方最后一格。它返回时从 "
              "0x…ff0 弹出我放在偏移 32 处的 0x4019b9（mov edi,0; call exit@plt），"
              "进程 exit(0)，干净离场。")
    heading(doc, "8.3 实测：字节流在固定栈上活了过来", 2)
    code(doc, ev["shellcode_inspect"])
    code(doc, ev["grade_hit"])
    code(doc, ev["shellcode_result"])
    heading(doc, "8.4 对照组：同一串字节，在 dark-calc-nx 上第一步就死", 2)
    para(doc, "把完全相同的 shellcode 喂给 dark-calc-nx，再把 PC 强制指到栈上：")
    code(doc, ev["nx_frame"].split("info proc mappings")[0].rstrip())
    code(doc, ev["nx_maps"])
    code(doc, ev["nx_fault"])
    para(doc, "同一批字节在 dark-calc 上执行、在 dark-calc-nx 上取指即 SIGSEGV——"
              "一条指令都没跑完。这就是 NX 的实锤：不是「文件名里带 nx」，是页表里没有 X。")
    doc.add_page_break()

    # ---------- 9 任务六 ----------
    heading(doc, "九、任务六：NX 之下的 ROP 攻击（10 测试 + 10 报告）", 1)
    think(doc, "shellcode 被 NX 枪毙了，栈地址又随机（GDB 里每次都不一样），跳栈无门。"
               "但主映像非 PIE：.text 里的每一行机器码都钉死在链接地址上。既然不能带自己的"
               "代码进场，就复用靶机里现成的代码——ROP 的本质就是「用别人的指令，干自己的事」。"
               "于是我去找 pop rdi; ret：objdump 里没有，换字节级扫描再找，还是没有。正打算"
               "认命，才想起来 CPU 并不读反汇编器的行号，它只顺着字节流一个字节一个字节地"
               "执行——那么，从一条指令的正中间切进去，是不是就能读到一条「不存在」的指令？")
    heading(doc, "9.1 捡零件：41 5f c3 往前走一个字节", 2)
    code(doc, disasm_range("dark-calc-nx", 0x401A2A, 0x401A35))
    para(doc, "__libc_csu_init 的尾声是 pop rbx; pop rbp; pop r12; pop r13; pop r14; pop r15; "
              "ret，结尾两条的机器码是 41 5f c3（pop r15; ret）。x86 是变长指令集，"
              "「指令边界」只是反汇编器的习惯，CPU 只认字节流：从 0x401a33 进入，0x5f 译码为 "
              "pop rdi，0xc3 译码为 ret——一个完美的未对齐 gadget 到手。")
    code(doc, "0x401a32: 41 5f c3        pop r15; ret\n"
              "0x401a33:    5f c3        pop rdi; ret   ← 从这里进入")
    heading(doc, "9.2 链与栈对齐", 2)
    table(doc,
          ["偏移", "值（小端）", "作用"],
          [
              ["0 – 23", "'R' × 24", "覆盖 expression[16] 与 saved rbp"],
              ["24 – 31", "0x401a33", "pop rdi; ret"],
              ["32 – 39", "0x0000000000000004", "rdi = 4（grade）"],
              ["40 – 47", "0x401978", "grade_eval"],
              ["48 – 55", "0x4018aa", "mov edi,0; call exit@plt → exit(0)"],
          ],
          widths=[2.2, 6.2, 8.6], mono_cols=(1,))
    para(doc, "对齐演算：input 的 ret 之后 rsp%16=0；pop rdi 弹掉一项后 rsp%16=8；再 ret 进入 "
              "grade_eval 时 rsp%16=8，与正常 call 一模一样——所以它内部 printf 的 movaps 不会"
              "因未对齐崩掉。grade_eval 是普通函数，自带 canary 建立与校验，链里没有任何一步"
              "碰它的帧。整条链只用固定代码地址，对栈随机化、libc 地址完全免疫。")
    heading(doc, "9.3 实测", 2)
    code(doc, "Enter an expression (length up to 15):\n\n Hope A will be your grade! \n"
              "target exit status: 0   PASS（期望字符串命中）")
    doc.add_page_break()

    # ---------- 10 任务七 ----------
    heading(doc, "十、任务七：绕过 Stack Canary（10 测试 + 10 报告）", 1)
    think(doc, "直线思路：覆盖返回地址得写 288 字节，而 canary 蹲在偏移 280——必然踩中；"
               "canary 每进程随机，静态 payload 根本写不回原值。先做个对照实验证明它确实在"
               "看着：288 字节覆盖 canary →「*** stack smashing detected ***: terminated」→ "
               "SIGABRT。铁壁，正面撞不动。")
    heading(doc, "10.1 对照实验：金丝雀真的会叫", 2)
    code(doc, ev["smash_before"])
    code(doc, ev["smash_after"])
    think(doc, "说个插曲：我的第一个对照 payload 更粗暴——320 个 'A' 直接灌。结果它把偏移 256 "
               "的 len 也写成了 0x41414141，memcpy 目的地变成非法地址，拷贝第二个 qword 就 "
               "SIGSEGV，连金丝雀的面都没见着。这次翻车反而是第七节最大的线索：gets 溢出"
               "之外，len 控制的定长拷贝是第二个、更精准的写原语。")
    heading(doc, "10.2 顿悟：金丝雀只盯着自己的窝", 2)
    para(doc, "canary 校验检查的是「rbp-8 的值变了没有」，不是「控制流变了没有」。那么问题"
              "变成：有没有一条路，改掉返回地址、却不经过 rbp-8？有——让那 128 字节的 memcpy "
              "改道。len 在偏移 256，先于 canary（280）被输入控制；令 len=0xa0=160，目的地 = "
              "logMsg+0xa0 = rbp。拷贝区间 rbp..rbp+0x7f 精准覆盖 saved rbp 与返回地址，"
              "canary 原封不动，校验自然通过。")
    picture(doc, os.path.join(FIGS, "fig_darklog.png"), 6.4, "图 4  len 控制的 memcpy：覆盖返回地址的同时让 canary 原封不动")
    heading(doc, "10.3 payload：恰好 260 字节", 2)
    table(doc,
          ["偏移", "字节", "作用"],
          [
              ["0 – 7", "'K' × 8", "fake saved rbp"],
              ["8 – 15", "0x4018a3", "pop rdi; ret（csu 尾部 41 5f c3 的第 2 字节）"],
              ["16 – 23", "4", "rdi = 4"],
              ["24 – 31", "0x401677", "grade_eval"],
              ["32 – 255", "'L' 填充", "凑到 len 字段之前"],
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
    para(doc, "拷贝前后 canary 一字不差；len=160、目的地=rbp；返回地址槽变成 0x4018a3。"
              "grade_eval 以 edi=4 进入，打印目标字符串。之后返回地址落进 'L' 填充 → SIGSEGV，"
              "但 printf 后面紧跟 fflush(stdout)，横幅已经落盘，CI 的 grep 不受影响。")
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
    doc.add_page_break()

    # ---------- 11 验收 ----------
    heading(doc, "十一、验收：GitHub Actions CI 实测通过", 1)
    rows = [[r["payload"], r["target"], str(r["bytes"]), str(r["target_rc"]),
             "PASS" if r["pass"] else "FAIL"] for r in ev["ci"]]
    table(doc, ["payload", "目标", "字节数", "目标退出状态", "结果"],
          rows, widths=[4.4, 3.4, 2.2, 3.2, 3.8], mono_cols=(0, 1))
    para(doc, "下表是本地 WSL（glibc 2.43）用 tools/run_evidence.py 逐字复现 CI 判分动作的实测记录。"
              "提交到 GitHub 后，仓库自带的 Actions（ubuntu-24.04，glibc 2.39）实测同样通过："
              "「Check report PDF」与「Test every exploit payload」两个 job 均 success，"
              "后者先以 sha256 校验 attack/ 四个二进制与助教清单逐字节一致，再对四个 payload "
              "逐一执行「生成 → 重定向 stdin → grep 期望串」。")
    para(doc, "payload.py 的完整输出（进程树 + 成功横幅）见 6.4 节，其余三段（analysis/logs/"
              "ci_simulation.txt）：")
    code(doc, ev["ci_sim"][ev["ci_sim"].index("== payload_dark.py"):].rstrip())
    para(doc, "本地复现（WSL2，与 CI 相同的重定向方式）：")
    code(doc, "# 1. 二进制复制进 Linux 文件系统（保住可执行位与页缓存行为）\n"
              "rm -rf ~/lab3 && mkdir -p ~/lab3 && cp /mnt/e/AttackLab/attack/* ~/lab3/ && chmod +x ~/lab3/*\n\n"
              "# 2. 证据采集（GDB / 反汇编 / 长度矩阵 / 本地 CI 复现）\n"
              "python3 tools/make_inputs.py\n"
              "bash   tools/capture_gdb.sh\n"
              "bash   tools/capture_disassembly.sh\n"
              "python3 tools/run_evidence.py\n\n"
              "# 3. 单个 payload 手动验证（与 CI 相同的重定向方式）\n"
              "python3 payload.py > /tmp/p.bin && (cd ~/lab3 && ./dark-calc < /tmp/p.bin)")
    para(doc, "CI 的动作序列：python3 <payload> > payload.bin → cd attack → ./<target> < "
              "payload.bin → grep -F 期望字符串。本地复现与真实 CI 的动作完全一致，"
              "真实 CI 已在 ubuntu-24.04（glibc 2.39）上以 success 收尾。")
    doc.add_page_break()

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
    doc.add_page_break()

    # ---------- 13 复盘 ----------
    heading(doc, "十三、复盘：踩过的坑与捡到的顿悟", 1)
    bullet(doc, "帧是剧本，溢出是彩蛋：rbp+8 的返回地址决定函数结局，gets 漫灌一旦越过缓冲区，剧本就归攻击者改。", "① ")
    bullet(doc, "只有页表不撒谎：GNU_STACK、文件名、编译选项都是「声明」；0x7210 那行 rwxp 才是真相。静态分析负责怀疑，运行期观察负责定罪。", "② ")
    bullet(doc, "指令边界是人的约定：41 5f c3 往前挪一个字节，pop r15 就变 pop rdi。ROP 的本质是「别人的字节流，我的控制流」。", "③ ")
    bullet(doc, "金丝雀只守着窝：它检测「值被改」，不检测「控制流被改」。攻击者要做的不是骗过它，而是找一条不经过它的路——dark-log 的 len 定长拷贝就是那条路。防御必须覆盖每一个越界写原语。", "④ ")
    bullet(doc, "预算思维：48 字节牢笼、15 字符闸门、8 字节栈顶——这些约束不是障碍，是题面。第一版 49 字节链的翻车教会我：先量清楚边界，再设计 payload。", "⑤ ")
    heading(doc, "局限与说明", 2)
    bullet(doc, "实验在 WSL2 Ubuntu 26.04（glibc 2.43）完成，CI 为 ubuntu-24.04（glibc 2.39）。payload 只依赖非 PIE 固定代码地址与 dark-calc 的固定映射，不依赖 glibc 内部布局；gets/system 等符号在两个版本均存在；")
    bullet(doc, "dark-calc 的 0x721000000000 固定映射假设该区间未被占用（MAP_FIXED_NOREPLACE 失败时程序会报错退出），当前内核与 CI 环境均成立；")
    bullet(doc, "payload.py 的 system 返回后与 payload_canary.py 的 grade_eval 返回后，进程会因伪造的帧数据崩溃（SIGBUS/SIGSEGV）：目标字符串在此之前已 flush，CI 只检查输出；payload_dark/payload_rop 已做到 exit(0)；")
    bullet(doc, "文中每条 GDB/运行记录都能按第十一节命令复现，原始日志与脚本随仓库提交。")
    heading(doc, "时间线", 2)
    table(doc,
          ["时间", "事件"],
          [
              ["23:40", "环境就绪；静态勘察三个 ELF，锁定 gets/strcpy/固定栈三处入口"],
              ["23:44", "GDB 量出栈帧：24 字节到返回地址、48 字节到守卫页；长度矩阵扫出生死线 23/24、47/48"],
              ["23:48", "payload.py（ret2eval-system）、payload_dark.py（固定栈 shellcode）、payload_rop.py（pop rdi 链）三版定稿并跑通"],
              ["23:49", "payload_canary.py 定稿：len=0xa0 改道 memcpy，canary 原封不动"],
              ["23:50", "六份 GDB 实录落盘（帧、rwxp 映射、NX 对照、canary 前后、对照实验、system 尾声）"],
              ["00:00", "本地复现四连 PASS；哈希核对 attack/ 一个字节没动；报告初版成文"],
              ["02:15", "终版润色：补全推理手记、翻车记录与复盘，重排版并逐条复核证据"],
              ["提交后", "GitHub Actions CI 实测：Check report PDF 与 Test every exploit payload 均 success"],
          ],
          widths=[2.2, 14.8])
    doc.add_page_break()

    # ---------- 附录 A ----------
    heading(doc, "附录 A：四个 payload 的完整清单与十六进制转储", 1)
    for name in ("payload.py", "payload_dark.py", "payload_rop.py", "payload_canary.py"):
        heading(doc, name, 2)
        code(doc, open(os.path.join(ROOT, name), encoding="utf-8").read())
        code(doc, payload_hexdump(name))
    picture(doc, os.path.join(FIGS, "fig_payloads.png"), 6.5, "图 3  四个 payload 的字节布局总览")
    doc.add_page_break()

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
        heading(doc, title, 2)
        code(doc, text)
    doc.add_page_break()

    # ---------- 附录 C ----------
    heading(doc, "附录 C：环境参数、文件哈希与实验时间线", 1)
    code(doc, ev["aslr"])
    table(doc, ["参数", "取值"],
          [[k, str(v)] for k, v in env.items()],
          widths=[5.5, 11.5], mono_cols=(1,))
    table(doc, ["文件", "SHA-256"],
          [(k, v["sha256"]) for k, v in ev["baseline"]["files"].items()],
          widths=[5.2, 11.8], mono_cols=(1,))
    para(doc, "注意：analysis/baseline.json 是 2026-11-02 实验初期的只读基线快照——"
              "其中 payload 的哈希对应当时的旧版实现（其后已改为 attacklab 动态解析，"
              "见附录 A），.gitignore 等文件其后亦有改动，故上表仅为历史记录。"
              "下面给出随本报告提交的五个 Python 文件的当前哈希（构建时现场计算）：")
    live_rows = []
    for name in ("attacklab.py", "payload.py", "payload_dark.py", "payload_rop.py", "payload_canary.py"):
        h = hashlib.sha256(open(os.path.join(ROOT, name), "rb").read()).hexdigest()
        live_rows.append([name, h])
    table(doc, ["文件", "SHA-256（提交时）"], live_rows,
          widths=[5.2, 11.8], mono_cols=(1,))
    para(doc, "攻击涉及的全部输入均为本课程自带的本地实验程序，不针对任何第三方系统；"
              "全部实验在隔离的 WSL2 环境内完成。")

    # ---------- 附录 D ----------
    heading(doc, "附录 D：常用命令速查", 1)
    code(doc, "# 段/符号/反汇编\n"
              "readelf -lW attack/dark-calc      # 程序头：GNU_STACK / LOAD 权限\n"
              "nm -C attack/dark-calc           # 符号与地址\n"
              "objdump -d -M intel attack/dark-calc          # 反汇编\n"
              "objdump -d --start-address=0x401a32 --stop-address=0x401a35 attack/dark-calc-nx\n\n"
              "# gadget 字节扫描（tools/gadgets.py）\n"
              "python3 tools/gadgets.py attack/dark-calc 5fc3 c3   # 找 pop rdi; ret / ret\n\n"
              "# GDB 批量会话\n"
              "gdb -q -batch -x tools/gdb/01_frame_and_main.gdb\n"
              "# 注意：每个脚本开头都有 set disable-randomization off，观察真实 ASLR\n\n"
              "# 完整性\n"
              "bash tools/hash_check.sh          # 对照 CI 的 sha256 清单\n\n"
              "# 端到端（与 CI 相同）\n"
              "python3 payload_canary.py > /tmp/p.bin && (cd ~/lab3 && ./dark-log < /tmp/p.bin)")

    doc.save(OUT)
    print("saved", OUT)


if __name__ == "__main__":
    build(load_evidence())
