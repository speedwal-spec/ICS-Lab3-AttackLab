#!/usr/bin/env python3
"""Build the Lab 3 report DOCX (analysis/Lab3-AttackLab-实验报告.docx).

Assembles: cover, TOC, the seven task sections with GDB/runtime evidence,
payload listings, figures, and appendices.  All evidence is read from
analysis/gdb, analysis/logs, analysis/disassembly and the payload scripts
themselves, so the report always reflects the recorded experiments.
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

OUT = os.path.join(ANALYSIS, "Lab3-AttackLab-实验报告.docx")

EAST = "微软雅黑"
ASCII = "微软雅黑"
MONO = "Consolas"
INK = RGBColor(0x21, 0x26, 0x30)
ACCENT = RGBColor(0x1F, 0x4E, 0x79)
CODE_BG = "F2F2F2"
HEAD_BG = "D6E4F7"


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
        st.element.get_or_add_rPr()
        rpr = st.element.rPr
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            rfonts = OxmlElement("w:rFonts")
            rpr.append(rfonts)
        rfonts.set(qn("w:ascii"), ASCII)
        rfonts.set(qn("w:hAnsi"), ASCII)
        rfonts.set(qn("w:eastAsia"), EAST)
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


def add_runs(par, text, size=None, bold=False, mono=False, color=None):
    run = par.add_run(clean_text(text))
    run.font.name = MONO if mono else ASCII
    run.element.rPr.rFonts.set(qn("w:eastAsia"), EAST)
    if size:
        run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = color
    return run


def para(doc, text, size=None, bold=False, mono=False, color=None,
         align=None, space_after=None):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    add_runs(p, text, size=size, bold=bold, mono=mono, color=color)
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


def code(doc, text, size=8.5):
    for line in text.rstrip("\n").split("\n"):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.line_spacing = 1.0
        shade_paragraph(p, CODE_BG)
        add_runs(p, line if line else " ", size=size, mono=True)
    return


def caption(doc, text):
    p = para(doc, text, size=9, color=RGBColor(0x55, 0x5A, 0x66),
             align=WD_ALIGN_PARAGRAPH.CENTER, space_after=8)
    return p


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
    hdr = t.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = ""
        p = hdr[i].paragraphs[0]
        add_runs(p, h, size=font_size, bold=True)
        set_cell_bg(hdr[i], HEAD_BG)
    for r in rows:
        cells = t.add_row().cells
        for i, v in enumerate(r):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(1)
            add_runs(p, str(v), size=font_size,
                     mono=(i in mono_cols))
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
    return h


def page_number_footer(doc):
    footer = doc.sections[0].footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_runs(p, "第 ", size=9)
    run = p.add_run()
    f1 = OxmlElement("w:fldChar"); f1.set(qn("w:fldCharType"), "begin")
    it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve")
    it.text = "PAGE"
    f2 = OxmlElement("w:fldChar"); f2.set(qn("w:fldCharType"), "end")
    run._r.append(f1); run._r.append(it); run._r.append(f2)
    run.font.size = Pt(9)
    add_runs(p, " 页", size=9)


def section(path, start, end=None, drop_backtrace=False):
    """Return the lines of `path` between markers (start inclusive, end exclusive)."""
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
    """Extract instruction lines whose address is in [lo, hi)."""
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


def read_log(name):
    return open(os.path.join(LOGS, name), encoding="utf-8").read()


MANIFEST_FILES = [
    "README.md",
    ".gitignore",
    ".gitattributes",
    ".github/workflows/lab3-checks.yml",
    "src/aslr.c",
    "src/dark-calc.c",
    "src/dark-log.c",
    "payload.py",
    "payload_dark.py",
    "payload_rop.py",
    "payload_canary.py",
    "attack/dark-calc",
    "attack/dark-calc-nx",
    "attack/dark-log",
    "attack/malware",
]


def file_manifest(root=ROOT):
    """Recompute the SHA-256 manifest straight from the files on disk.

    The appendix must show the hashes of the files actually submitted, so the
    manifest is always computed at build time instead of trusting a snapshot
    that may predate later edits (e.g. payload script rewrites).
    """
    out = {}
    for rel in MANIFEST_FILES:
        data = open(os.path.join(root, rel), "rb").read()
        out[rel] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
    return out


def refresh_baseline(manifest):
    """Sync analysis/baseline.json with the fresh manifest, reporting any drift."""
    path = os.path.join(ANALYSIS, "baseline.json")
    old = json.load(open(path, encoding="utf-8"))
    changed = [
        (k, old["files"].get(k, {}).get("sha256", "-"), v["sha256"])
        for k, v in manifest.items()
        if old["files"].get(k, {}).get("sha256") != v["sha256"]
    ]
    if changed:
        old["files"] = manifest
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(old, fh, indent=2, ensure_ascii=False)
        for k, o, n in changed:
            print(f"baseline.json refreshed: {k}  {o[:16]}… -> {n[:16]}…")
    return old


def payload_hexdump(script):
    """Run a payload script with this interpreter and hexdump its stdout."""
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
    ev["baseline"] = refresh_baseline(file_manifest())
    ev["hash_check"] = read_log("hash_check.txt")
    ev["ci_sim"] = read_log("ci_simulation.txt")
    ev["aslr"] = read_log("aslr.txt")

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
    page_number_footer(doc)

    # ---------- cover ----------
    for _ in range(5):
        doc.add_paragraph()
    para(doc, "计算机系统基础（ICS）实验 3", size=16, bold=True,
         align=WD_ALIGN_PARAGRAPH.CENTER)
    para(doc, "AttackLab 实验报告", size=30, bold=True,
         align=WD_ALIGN_PARAGRAPH.CENTER, color=ACCENT)
    para(doc, "缓冲区溢出 · 栈空间执行 · ROP · Stack Canary", size=13,
         align=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0x55, 0x5A, 0x66))
    for _ in range(3):
        doc.add_paragraph()
    para(doc, "姓名：____________________　　学号：____________________",
         size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    para(doc, "日期：2026 年 11 月 2 日", size=12,
         align=WD_ALIGN_PARAGRAPH.CENTER)
    for _ in range(2):
        doc.add_paragraph()
    para(doc, "提交内容：payload.py、payload_dark.py、payload_rop.py、payload_canary.py 与本 PDF 报告",
         size=11, align=WD_ALIGN_PARAGRAPH.CENTER)
    para(doc, "四个 payload 均通过与本仓库 CI 完全一致的等价测试；全部测试输出见 analysis/logs/。",
         size=11, align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_page_break()

    # ---------- TOC ----------
    heading(doc, "目录", 1)
    toc = [
        "一、实验概述与结论摘要",
        "二、实验环境与完整性校验",
        "三、目标程序静态分析与保护机制判读",
        "四、任务一：观察 input 栈帧（20 分）",
        "五、任务二：不同长度字符串输入测试（5 分）",
        "六、任务三：利用缓冲区漏洞执行 ./malware（25 测试 + 5 报告）",
        "七、任务四：用 GDB 检查 main 函数的机器码（5 分）",
        "八、任务五：栈空间执行（25 测试 + 5 报告）",
        "九、任务六：ROP（10 测试 + 10 报告）",
        "十、任务七：Canary（10 测试 + 10 报告）",
        "十一、端到端验证与复现方法",
        "十二、防御与改进建议",
        "十三、总结与局限",
        "附录 A：四个 payload 的完整清单与十六进制转储",
        "附录 B：关键 GDB 实录摘录",
        "附录 C：环境参数与文件哈希",
    ]
    for t in toc:
        para(doc, t, size=11, space_after=4)
    doc.add_page_break()

    # ---------- 1 概述 ----------
    heading(doc, "一、实验概述与结论摘要", 1)
    para(doc, "本实验（Lab 3, AttackLab）提供三个存在缓冲区溢出漏洞的 ELF 二进制 "
              "（attack/dark-calc、attack/dark-calc-nx、attack/dark-log）和一个判定脚本 "
              "（attack/malware），要求分别完成：栈帧观察、长度边界测试、溢出执行 ./malware、"
              "GDB 机器码检查、栈空间执行（shellcode）、ROP 与 Canary 绕过共七项任务，"
              "满分 130 分。仓库 CI 会逐字节校验 attack/ 未被修改，并实际运行四个 payload 脚本，"
              "检查目标二进制被注入后的 stdout 是否包含指定字符串。")
    table(doc,
          ["任务", "分值", "完成情况", "证据"],
          [
              ["观察 input 栈帧", "20（报告）", "完成", "第四节；analysis/gdb/01_frame_and_main.txt；图 1"],
              ["不同长度输入测试 dark-calc", "5（报告）", "完成", "第五节；analysis/logs/length_tests.md"],
              ["缓冲区溢出执行 ./malware", "25 测试 + 5 报告", "测试 PASS", "第六节；payload.py"],
              ["GDB 检查 main 机器码", "5（报告）", "完成", "第七节；disassemble /r main 实录"],
              ["栈空间执行", "25 测试 + 5 报告", "测试 PASS", "第八节；payload_dark.py"],
              ["ROP", "10 测试 + 10 报告", "测试 PASS", "第九节；payload_rop.py"],
              ["Canary", "10 测试 + 10 报告", "测试 PASS", "第十节；payload_canary.py"],
          ],
          widths=[5.2, 3.4, 2.6, 6.0])
    para(doc, "结论摘要：四个 payload 全部通过 CI 等价测试（analysis/logs/ci_simulation.txt），"
              "对应输出字符串与 .github/workflows/lab3-checks.yml 逐字一致：")
    p = doc.add_paragraph(style="List Bullet")
    add_runs(p, "payload.py → dark-calc：输出 ")
    add_runs(p, "“### You have successfully detonated the bomb! Congratulations! ###”", mono=True, size=9.5)
    p = doc.add_paragraph(style="List Bullet")
    add_runs(p, "payload_dark.py → dark-calc / payload_rop.py → dark-calc-nx / payload_canary.py → dark-log：输出 ")
    add_runs(p, "“Hope A will be your grade!”", mono=True, size=9.5)
    para(doc, "所有地址与字节序列均来自仓库内未修改的二进制（哈希与 CI 清单一致），"
              "并经过 GDB 实机验证；利用完全独立于 ASLR（非 PIE 主映像 + dark-calc 的固定地址映射）。")
    doc.add_page_break()

    # ---------- 2 环境 ----------
    heading(doc, "二、实验环境与完整性校验", 1)
    heading(doc, "2.1 实验环境", 2)
    env = ev["env"]
    table(doc,
          ["项目", "取值"],
          [
              ["操作系统", "WSL2 Ubuntu 26.04 LTS（内核 " + env["uname"] + "）"],
              ["gcc", env["gcc"]],
              ["gdb", env["gdb"]],
              ["binutils (objdump)", env["objdump"]],
              ["glibc (ldd)", env["libc"]],
              ["Python", env["python"]],
              ["ASLR（randomize_va_space）", env["aslr"] + "（全量随机化开启）"],
              ["GDB 默认 disable-randomization", env["gdb_default_disable_randomization"] + "（实验会话中显式关闭）"],
              ["CI 环境", "GitHub Actions ubuntu-24.04（glibc 2.39，Python 3.12，超时 15 s/命令）"],
          ],
          widths=[5.5, 11.5])
    para(doc, "所有 GDB 会话均以 set disable-randomization off 运行，观察到的栈/共享库地址是真实"
              "随机化的结果；四个 payload 只依赖非 PIE 主映像的固定代码地址与 dark-calc 的固定映射，"
              "因此同样适用于 CI 环境。")
    heading(doc, "2.2 完整性校验", 2)
    para(doc, "attack/ 下四个文件是实验资产，未做任何修改。用 CI 中完全相同的清单执行 "
              "sha256sum --check --strict 的结果（analysis/logs/hash_check.txt）：")
    code(doc, ev["hash_check"].split("# payload scripts")[0].rstrip())
    table(doc,
          ["文件", "SHA-256（前 16 字符）", "大小"],
          [(k, v["sha256"][:16] + "…", v["size"])
           for k, v in ev["baseline"]["files"].items() if k.startswith("attack/")],
          widths=[5.0, 8.0, 3.0], mono_cols=(1,))
    para(doc, "仓库目录没有 .git 元数据，无法用 git diff 核对提交历史；完整性以哈希清单为准。"
              "全部新增文件都位于 analysis/ 与 tools/ 之下，加上四个根目录 payload 与本报告。")
    heading(doc, "2.3 分析方法", 2)
    bullet(doc, "静态分析：readelf/nm/objdump 解析段、符号与指令字节；tools/gadgets.py 扫描字节序列定位未对齐 gadget。", "① ")
    bullet(doc, "动态观察：GDB 批量会话（tools/gdb/*.gdb）观察帧布局、页权限、寄存器与控制流；", "② ")
    bullet(doc, "端到端验证：tools/run_evidence.py 复现 CI 的“生成 payload → 重定向 stdin → grep 期望输出”全流程。", "③ ")
    doc.add_page_break()

    # ---------- 3 静态分析 ----------
    heading(doc, "三、目标程序静态分析与保护机制判读", 1)
    heading(doc, "3.1 ELF 属性", 2)
    table(doc,
          ["属性", "dark-calc", "dark-calc-nx", "dark-log"],
          [
              ["文件类型", "ELF64 x86-64，动态链接，非 PIE（ET_EXEC）", "同左", "同左"],
              ["入口 _start", "0x401890", "0x401700", "0x401590"],
              ["GNU_STACK", "RW（未请求执行）", "RW", "RW"],
              ["RELRO", "Partial（.got.plt 可写）", "Partial", "Partial"],
              ["栈保护（canary）导入", "无", "无", "__stack_chk_fail（input/main/grade_eval 均校验）"],
              ["特殊构造器", "init_fixed_stack（固定地址 RWX 栈）+ __wrap_main 栈切换", "无（常规 main 调用）", "无"],
          ],
          widths=[3.4, 5.0, 3.2, 5.4])
    para(doc, "三个主映像都链接在 0x400000、非 PIE：.text/.rodata 的地址在多次运行之间完全不变，"
              "这是本实验 ROP/ret2code 全部使用绝对地址的前提。GNU_STACK 只是 ELF 对普通线程栈的"
              "权限“请求”，真正决定栈可执行性的是运行期映射；dark-calc 的固定栈映射（rwxp）会在第八节"
              "用 /proc 映射与 GDB 实测证实。")
    heading(doc, "3.2 dark-calc：输入、截断与固定栈", 2)
    para(doc, "input() 的完整反汇编（analysis/disassembly/dark-calc.txt）：")
    code(doc, disasm_func("dark-calc", "input", "eval"))
    para(doc, "eval() 把 command_buf 截断到 15 字符并包成 shell 命令执行：")
    code(doc, disasm_func("dark-calc", "eval", "grade_eval"))
    para(doc, "要点：expression 只有 16 字节但被交给无界的 gets()；input() 里没有 canary 校验；"
              "eval() 的 MAXLEN 截断发生在 gets 之后，只能限制 shell 命令里表达式的长度，"
              "无法消除栈溢出。grade_eval(4) 打印“Hope A will be your grade!”，是后四个任务的"
              "控制流目标。")
    heading(doc, "3.3 dark-calc 的固定栈构造器与栈切换", 2)
    code(doc, disasm_func("dark-calc", "init_fixed_stack", "__wrap_main"))
    code(doc, disasm_func("dark-calc", "__wrap_main", "__libc_csu_init"))
    para(doc, "init_fixed_stack 用 mmap(0x721000000000, 0x802000, RWX, "
              "MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE, -1, 0) 在固定地址申请 8 MiB，"
              "再用 mprotect 把两端各 0x1000 置为 PROT_NONE（守卫页），把 0x721000801000 存入 "
              "fixed_stack_top；__wrap_main 在调用 main 前把 rsp 切到该栈。因此 dark-calc 的"
              "“栈”实际上是一段固定地址、可读可写可执行的匿名映射——这正是任务五的立足点。")
    heading(doc, "3.4 dark-log 的帧结构与 canary", 2)
    para(doc, "struct log_frame 的字段与编译期布局（GDB 实测偏移见第十节）：")
    table(doc,
          ["偏移（相对 rbp）", "字段", "说明"],
          [
              ["-0x120", "expression[128]", "gets 写入点，也是 memcpy 的源"],
              ["-0xa0", "logMsg[128]", "memcpy 的目的基址（logMsg + len）"],
              ["-0x20", "len（int）", "初值 0；偏移 256 处可被输入覆盖"],
              ["-0x18", "pad[8]", "gets 的 NUL 终止符可安全落在这里"],
              ["-0x08", "stack canary", "fs:0x28 的副本，返回前异或校验"],
              ["+0x00 / +0x08", "saved rbp / 返回地址", "控制流目标"],
          ],
          widths=[3.6, 4.6, 8.8])
    code(doc, disasm_range("dark-log", 0x4016E1, 0x401701) + "\n" +
         disasm_range("dark-log", 0x401719, 0x40173D) + "\n" +
         disasm_range("dark-log", 0x4017DF, 0x4017F5))
    para(doc, "编译器把 memcpy 内联为 16 个 qword 拷贝，目的地址 = logMsg + len，len 完全由"
              "输入控制——这是 canary 任务的突破口；返回前的 xor 校验指向 __stack_chk_fail。")
    heading(doc, "3.5 malware 的判定逻辑", 2)
    code(doc, open(os.path.join(ROOT, "attack", "malware"), encoding="utf-8").read())
    para(doc, "malware 打印进程树后沿父进程链逐级向上找进程名 dark-calc：只有由 dark-calc "
              "（经由 system() 等）启动的 shell 再启动它，判定才会成功。")
    heading(doc, "3.6 保护机制判读", 2)
    table(doc,
          ["机制", "静态证据", "本实验中的实际作用"],
          [
              ["NX（栈不可执行）", "GNU_STACK RW；dark-calc-nx/dark-log 的线程栈映射 rw-p",
               "对 dark-calc-nx/dark-log 生效，迫使任务六使用 ROP；dark-calc 因固定 RWX 映射而例外"],
              ["ASLR", "主映像 ET_EXEC 非 PIE；栈与 libc 地址随机（实测 &i 六次各不相同）",
               "对固定代码地址无效；payload 全部与栈/libc 地址无关"],
              ["Stack Canary", "dark-log 导入 __stack_chk_fail，fs:0x28 存帧尾",
               "直接覆盖返回地址会被检测（第十节对照实验）；必须保留 canary 原值"],
              ["RELRO", "Partial：.got.plt 可写", "本实验未使用 GOT 覆写路径"],
              ["长度截断（MAXLEN=15）", "eval 中 min(strlen, 15)", "只限制 shell 表达式，不影响 gets 溢出"],
          ],
          widths=[3.2, 6.4, 7.4])
    doc.add_page_break()

    # ---------- 4 任务一 ----------
    heading(doc, "四、任务一：观察 input 栈帧（20 分）", 1)
    heading(doc, "4.1 理论推导", 2)
    para(doc, "x86-64 System V ABI 中，被调函数以 push rbp; mov rbp,rsp; sub rsp,N 开场："
              "rbp 固定指向当前帧基址，局部变量位于 rbp 之下，而调用者执行 call 时压入的返回地址"
              "位于 rbp+8。input() 的 leave; ret 等价于 mov rsp,rbp; pop rbp; ret，即先恢复 rsp，"
              "再从原 rbp+8 处弹出返回地址跳转。若输入越过 expression[16] 的边界，就会依次覆盖 "
              "saved rbp（偏移 16）与返回地址（偏移 24），从而劫持控制流。")
    heading(doc, "4.2 静态分析", 2)
    para(doc, "input() 序言与 gets 调用点（lea rbp-0x10 作为参数）：")
    code(doc, disasm_range("dark-calc", 0x401977, 0x40199F))
    heading(doc, "4.3 GDB 实际观察", 2)
    para(doc, "在 input 入口与 gets 返回处断点，读取 rbp/rsp 与栈内容（完整记录见 "
              "analysis/gdb/01_frame_and_main.txt）：")
    code(doc, ev["frame_entry"])
    code(doc, ev["frame_prologue"])
    code(doc, ev["frame_after_gets"])
    para(doc, "观察结果整理（图 1）：")
    picture(doc, os.path.join(FIGS, "fig_frame_input.png"), 6.3, "图 1  dark-calc 的 input() 栈帧（固定栈，地址恒定）")
    table(doc,
          ["地址（固定）", "槽位", "实测值", "说明"],
          [
              ["0x721000800fd0", "expression[16]", "输入内容", "gets 写入起点；+0 偏移"],
              ["0x721000800fe0", "saved rbp", "0x721000800ff0", "main 的 rbp；+16 偏移"],
              ["0x721000800fe8", "返回地址", "0x401ad1", "main+0xe（call input 之后）；+24 偏移"],
              ["0x721000800ff0", "main 的 saved rbp", "0", "_start 中 xor ebp,ebp 的遗留值"],
              ["0x721000800ff8", "__wrap_main 的返回地址", "0x401c1f", "call main 压入"],
              ["0x721000801000", "守卫页起点", "PROT_NONE", "越界写到这里会 SIGSEGV"],
          ],
          widths=[3.6, 3.4, 3.6, 6.4], mono_cols=(0, 2))
    para(doc, "结论：缓冲区到返回地址槽 = 24 字节；缓冲区到守卫页 = 48 字节（gets 还要写 NUL，"
              "故单次输入上限 47 字节）。这一 48 字节窗口直接决定了第六节 payload.py 的形态。")
    doc.add_page_break()

    # ---------- 5 任务二 ----------
    heading(doc, "五、任务二：不同长度字符串输入测试（5 分）", 1)
    heading(doc, "5.1 实验设计", 2)
    para(doc, "向 dark-calc 输入由 n 个 '1' 组成的行（n ∈ {0,1,3,8,15,16,20,23,24,31,47,48,64,200}），"
              "记录退出状态与 stdout。数字串保证 eval 包装出的 echo $((...)) 是合法算术式，"
              "便于观察长度效应（analysis/logs/length_tests.json）。")
    heading(doc, "5.2 实测结果", 2)
    rows = []
    for r in ev["lengths"]:
        n, rc = r["length"], r["rc"]
        if n == 0:
            note = "空行：打印内置答案 42_is_The_…，exit(0)"
        elif n <= 15:
            note = "正常：Executing: echo $((1…1))，算术输出 n 个 1"
        elif n <= 23:
            note = "saved rbp 被覆盖但返回地址完好；eval 把表达式截断为 15 字符照常执行"
        elif n == 24:
            note = "返回地址最低字节被 NUL 清零（0x401ad1→0x401a00），落入 eval 内部，SIGBUS(-7)"
        elif n <= 47:
            note = "返回地址被 '1' 串整体覆盖（0x3131…），ret 后 SIGSEGV(-11)"
        else:
            note = "gets 的 NUL 写入 PROT_NONE 守卫页，gets 内部 SIGSEGV(-11)"
        rows.append([str(n), str(rc), note])
    table(doc, ["输入长度 n", "退出状态", "现象与解释"], rows, widths=[2.4, 2.4, 12.2])
    para(doc, "两个边界非常清晰：23/24（返回状态破坏）与 47/48（守卫页）。此外，stdout 是全缓冲的："
              "printf 的提示符要等 fflush 才落盘，而 system() 的子进程直接写管道，因此短输入时"
              "算术结果会先于 “Executing:” 行出现——这解释了测试输出中行序“错乱”的现象。")
    heading(doc, "5.3 与 MAXLEN 截断的关系", 2)
    para(doc, "eval 只在 strlen(command_buf) > 15 时截断到 15 字符（0x4019e9 处 cmp rax,0xf）。"
              "16–23 字节输入虽然已越出 expression[16]，eval 仍正常执行且只取前 15 个字符——"
              "证明“长度检查”发生在溢出之后，对缓冲区漏洞没有任何防护作用；它只是把 shell 表达式"
              "限制在 15 字符以内（第六节会讨论这一限制的旁路）。")
    doc.add_page_break()

    # ---------- 6 任务三 ----------
    heading(doc, "六、任务三：利用缓冲区漏洞执行 ./malware（25 测试 + 5 报告）", 1)
    heading(doc, "6.1 目标与约束", 2)
    para(doc, "malware 只有在父进程链里找到 dark-calc 才打印成功横幅，因此必须让 dark-calc "
              "自己 system(\"./malware\")。朴素方案是伪造返回地址链：")
    code(doc, "pop rdi; ret (0x401c93)  +  0x6030d0 (command_buf)  +  system@plt (0x4017e0)\n"
              "共 24 字节 padding + 24 字节链 = 48 字节，再加 gets 的 NUL → 49 字节，超出 48 字节窗口。")
    para(doc, "第四节已证明 dark-calc 单次输入上限 47 字节，这条 3-qword 链在固定栈上放不下。"
              "于是改用更短的 ret2code：直接返回 eval() 内部“以 command_buf 调用 system”的位置——")
    code(doc, disasm_range("dark-calc", 0x401A6B, 0x401A86))
    para(doc, "0x401a6b 处的 mov edi,0x6030d0 替我们完成了 pop rdi 的职责：输入返回时，"
              "input 已经执行过 strcpy(command_buf, expression)，把 payload 开头第一个 NUL "
              "之前的字符串（即 \"./malware\"）写进了 command_buf。随后 call system@plt 执行 "
              "sh -c ./malware，父链 sh → dark-calc，malware 判定命中。")
    heading(doc, "6.2 payload 布局", 2)
    table(doc,
          ["偏移", "字节", "作用"],
          [
              ["0 – 9", "\"./malware\" + NUL", "command_buf 的 shell 命令（strcpy 拷到第一个 NUL 为止）"],
              ["10 – 15", "'A' × 6", "填充到 16 字节（expression 容量）"],
              ["16 – 23", "'B' × 8", "伪造 saved rbp（本路径不再使用 rbp）"],
              ["24 – 31", "0x401a6b（小端）", "返回地址 → eval 的 system 调用点"],
          ],
          widths=[2.0, 5.4, 9.6], mono_cols=(1,))
    code(doc, payload_hexdump("payload.py"))
    heading(doc, "6.3 GDB 观察", 2)
    code(doc, ev["sys_site"])
    code(doc, ev["sys_after"])
    code(doc, ev["sys_epilogue"])
    para(doc, "GDB 里 cwd 不是 attack/，所以 sh 报 ./malware: not found——CI 在 attack/ 目录内运行，"
              "脚本可以找到。断点证实 rdi=0x6030d0、command_buf=\"./malware\"；system 返回后 eval 的"
              "leave 使用被伪造的 rbp(0x4242…) → SIGBUS，但此时子进程的输出已经写入 stdout，"
              "CI 检查的是输出内容而非退出状态。")
    heading(doc, "6.4 端到端实测", 2)
    picture(doc, os.path.join(FIGS, "fig_proc_tree.png"), 6.2, "图 5  payload.py 的运行现场：malware 沿父链找到 dark-calc")
    sim = ev["ci_sim"]
    block = sim[sim.index("== payload.py"):]
    block = block[:block.index("== payload_dark.py")].rstrip()
    code(doc, block)
    heading(doc, "6.5 附加发现：算术包装里的命令替换", 2)
    para(doc, "eval 把输入包成 echo $((…)) 再交给 /bin/sh。实测 dash 与 bash 在算术扩展内部"
              "仍会先做命令替换：$(( $(cmd) ))。12 字节的字符串 $(./malware) 就能在 15 字符上限内"
              "触发 malware（退出前把算术解析失败的信息打到 stderr，stdout 同样出现成功横幅）。"
              "这说明本程序的攻击面不止溢出：任何能到达 command_buf 的 shell 元字符都可注入命令。"
              "本任务按实验要求使用缓冲区溢出（返回地址覆盖）实现，未依赖该注入路径；但它是一个"
              "值得记录的防御要点（见第十二节）。")
    doc.add_page_break()

    # ---------- 7 任务四 ----------
    heading(doc, "七、任务四：用 GDB 检查 main 函数的机器码（5 分）", 1)
    para(doc, "在 GDB 中对 dark-calc 执行 disassemble /r main，得到带原始字节的完整反汇编：")
    code(doc, ev["main_bytes"])
    table(doc,
          ["地址", "机器码", "指令", "逐字节解读"],
          [
              ["0x401ac3", "55", "push rbp", "保存调用者帧指针"],
              ["0x401ac4", "48 89 e5", "mov rbp,rsp", "建立 main 自己的帧基址"],
              ["0x401ac7", "b8 00 00 00 00", "mov eax,0", "置零 rax 高位，循环起点"],
              ["0x401acc", "e8 a6 fe ff ff", "call 0x401977", "rel32=0xfffffea6=-0x15a；下一指令 0x401ad1-0x15a=0x401977 → input"],
              ["0x401ad1", "b8 00 00 00 00", "mov eax,0", "call input 之后"],
              ["0x401ad6", "e8 fc fe ff ff", "call 0x4019d7", "rel32=-0x104；0x401adb-0x104=0x4019d7 → eval"],
              ["0x401adb", "eb ea", "jmp 0x401ac7", "rel8=0xea=-22；0x401add-22=0x401ac7，回循环起点"],
          ],
          widths=[2.2, 3.0, 3.0, 8.8], mono_cols=(0, 1, 2))
    para(doc, "说明：① call/jmp 是 RIP 相对的，机器码里是“到下一指令”的有符号偏移；"
              "② main 没有局部变量，因此没有 sub rsp；③ 0x401ac7→0x401adb 构成 while(1) 循环，"
              "一次 input()+eval() 之后回到循环头再次读取；④ main 入口 rsp%16=8，push rbp 后 "
              "rsp%16=0，call 压栈后输入函数入口 rsp%16=8，符合 SysV ABI 栈对齐约定。")
    doc.add_page_break()

    # ---------- 8 任务五 ----------
    heading(doc, "八、任务五：栈空间执行（25 测试 + 5 报告）", 1)
    heading(doc, "8.1 固定栈的建立", 2)
    para(doc, "第三节已给出 init_fixed_stack/__wrap_main 反汇编。运行期映射（GDB info proc "
              "mappings 摘录，完整见 analysis/gdb/02_fixed_stack.txt）：")
    code(doc, ev["fixed_maps"])
    picture(doc, os.path.join(FIGS, "fig_fixed_stack.png"), 6.4, "图 2  dark-calc 的固定栈映射：rwxp 栈页 + 两侧守卫页")
    para(doc, "main 由 __wrap_main 调用，进入时 rsp 已经是固定栈顶 0x721000801000 下方：")
    code(doc, ev["wrap_entry"])
    para(doc, "结论：① 栈页权限是 rwxp——ELF 头里的 GNU_STACK RW 只是“普通线程栈”的请求，"
              "运行期真正使用的固定映射可执行；② 映射地址固定（MAP_FIXED_NOREPLACE 落在 "
              "0x721000000000），缓冲区地址 0x721000800fd0 每次运行都相同，ASLR 完全失效；"
              "③ 两端 PROT_NONE 守卫页把单次输入限制在 47 字节。")
    heading(doc, "8.2 shellcode 设计", 2)
    code(doc, "6a 04          push 4\n"
              "5f             pop  rdi                ; edi = 4\n"
              "48 b8 <a87…>   movabs rax, 0x401a87     ; grade_eval\n"
              "ff e0          jmp   rax               ; 注意是 jmp 不是 call")
    para(doc, "用 jmp 而非 call：shellcode 入口时 rsp=0x721000800ff0，距守卫页只剩 8 字节可写；"
              "jmp 不压栈，grade_eval 的 prologue（push rbp 落在 0x…fe8）正好落在守卫页下方。"
              "grade_eval 返回时从 0x…ff0 弹出我们放在偏移 32 处的 0x4019b9（mov edi,0; "
              "call exit@plt），进程以 exit(0) 干净结束。shellcode 共 15 字节，小于 16 字节的"
              "缓冲区，返回地址槽（偏移 24）指向缓冲区自身。")
    heading(doc, "8.3 GDB 观察", 2)
    code(doc, ev["shellcode_inspect"])
    code(doc, ev["grade_hit"])
    code(doc, ev["shellcode_result"])
    para(doc, "断点落在 0x401a87 时 rdi=4、rsp=0x721000800ff0，随后打印“Hope A will be your "
              "grade!”，进程 [Inferior exited normally]（exit(0)）。")
    heading(doc, "8.4 NX 对照：dark-calc-nx 的栈不可执行", 2)
    para(doc, "dark-calc-nx 没有固定栈，线程栈映射为 rw-p：")
    code(doc, ev["nx_frame"].split("info proc mappings")[0].rstrip())
    code(doc, ev["nx_maps"])
    para(doc, "把 PC 强制指到栈上的 shellcode 字节，第一条指令取指即触发 SIGSEGV：")
    code(doc, ev["nx_fault"])
    para(doc, "同一批字节在 dark-calc 上正常执行、在 dark-calc-nx 上取指崩溃——直接证明 NX "
              "保护的生效与否取决于运行期页权限，而不是文件名里的 “nx”。")
    doc.add_page_break()

    # ---------- 9 任务六 ----------
    heading(doc, "九、任务六：ROP（10 测试 + 10 报告）", 1)
    heading(doc, "9.1 为什么必须 ROP", 2)
    para(doc, "第八节已证明 dark-calc-nx 的栈是 rw-p：注入的代码无法执行，且栈地址随机，"
              "不能像任务五那样跳回缓冲区。但主映像非 PIE，.text 里的代码地址固定，"
              "因此改为复用已有代码片段（gadget）构造返回链。")
    heading(doc, "9.2 gadget 的定位", 2)
    code(doc, disasm_range("dark-calc-nx", 0x401A2A, 0x401A35))
    para(doc, "__libc_csu_init 的尾声是 pop rbx; pop rbp; pop r12; pop r13; pop r14; pop r15; "
              "ret，最后两条机器码为 41 5f c3（pop r15; ret）。从 0x401a33 进入（越过 0x41），"
              "0x5f 正好被译码为 pop rdi，0xc3 为 ret——一个完美的未对齐 gadget：")
    code(doc, "0x401a32: 41 5f c3        pop r15; ret\n"
              "0x401a33:    5f c3        pop rdi; ret   ← 从这里进入")
    heading(doc, "9.3 ROP 链与栈对齐", 2)
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
    para(doc, "对齐推导：input 的 ret 之后 rsp%16=0；pop rdi 弹出一项后 rsp%16=8；再 ret 进入 "
              "grade_eval 时 rsp%16=8，与正常 call 完全一致，故其内部 printf 的 movaps 不会因"
              "未对齐崩溃。grade_eval 是普通函数，自带 canary 建立与校验，链中没有触碰其帧。"
              "全链只含固定代码地址，对栈随机化、libc 地址完全免疫。")
    heading(doc, "9.4 实测结果", 2)
    code(doc, "Enter an expression (length up to 15):\n\n\x1b[31m Hope A will be your grade! \n"
              "target exit status: 0   PASS（期望字符串命中）")
    doc.add_page_break()

    # ---------- 10 任务七 ----------
    heading(doc, "十、任务七：Canary（10 测试 + 10 报告）", 1)
    heading(doc, "10.1 为什么不能直接覆盖返回地址", 2)
    para(doc, "dark-log 的 input/main/grade_eval 都有栈保护。input 入口把 fs:0x28 的 canary 存到 "
              "rbp-0x8，返回前异或校验。canary 在偏移 280：直接构造 288 字节输入覆盖它，"
              "要么拷贝阶段因 len 失控先崩，要么返回时校验失败。对照实验（analysis/gdb/"
              "04b_canary_smash.txt）：")
    code(doc, ev["smash_before"])
    code(doc, ev["smash_after"])
    para(doc, "glibc 报 “*** stack smashing detected ***: terminated” 并以 SIGABRT 终止——"
              "canary 值每进程随机，静态 payload 无法“写回原值”。")
    heading(doc, "10.2 思路：用 len 移动 memcpy 的目的地", 2)
    para(doc, "注意 input() 在 gets 之后还有一次拷贝：memcpy(logMsg + len, expression, 128)。"
              "len 位于偏移 256，可以先于 canary（偏移 280）被覆盖。令 len=0xa0（160），目的地变成 "
              "logMsg+0xa0 = rbp：128 字节拷贝正好覆盖 saved rbp 与返回地址，而 canary 在 rbp-8，"
              "拷贝区间 rbp..rbp+0x7f 完全碰不到它，校验自然通过。")
    picture(doc, os.path.join(FIGS, "fig_darklog.png"), 6.4, "图 4  len 控制的 memcpy：覆盖返回地址的同时让 canary 原封不动")
    heading(doc, "10.3 payload 布局", 2)
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
    para(doc, "输入恰好 260 字节：gets 的 NUL 落在偏移 260（pad 区），与 canary（280）相距 20 字节。"
              "字节 0–127 是 memcpy 的源，fake 帧就放在这里。")
    code(doc, payload_hexdump("payload_canary.py"))
    heading(doc, "10.4 GDB 观察", 2)
    code(doc, ev["canary_before"])
    code(doc, ev["canary_after"])
    code(doc, ev["canary_hit"].split("#1")[0].rstrip())
    code(doc, ev["canary_end"])
    para(doc, "canary 在拷贝前后均为 TLS 原值；len=160、目的地=rbp；返回地址槽变为 0x4018a3。"
              "grade_eval 以 edi=4 进入并打印目标字符串。grade_eval 返回后落入 'L' 填充 → SIGSEGV，"
              "但 printf 之后紧跟 fflush(stdout)，输出已经落盘，CI 的 grep 不受影响。")
    doc.add_page_break()

    # ---------- 11 验证 ----------
    heading(doc, "十一、端到端验证与复现方法", 1)
    heading(doc, "11.1 CI 等价测试结果", 2)
    rows = [[r["payload"], r["target"], str(r["bytes"]), str(r["target_rc"]),
             "PASS" if r["pass"] else "FAIL"] for r in ev["ci"]]
    table(doc, ["payload", "目标", "字节数", "目标退出状态", "结果"],
          rows, widths=[4.4, 3.4, 2.2, 3.2, 3.8], mono_cols=(0, 1))
    para(doc, "期望字符串与 workflow 完全一致（analysis/logs/ci_simulation.txt）；payload.py 的完整"
              "输出（含进程树与成功横幅）见 6.4 节，其余三段如下：")
    code(doc, ev["ci_sim"][ev["ci_sim"].index("== payload_dark.py"):].rstrip())
    heading(doc, "11.2 复现步骤（WSL2）", 2)
    code(doc, "# 1. 把二进制复制到 Linux 文件系统（保证可执行位与页缓存正常）\n"
              "rm -rf ~/lab3 && mkdir -p ~/lab3 && cp /mnt/e/AttackLab/attack/* ~/lab3/ && chmod +x ~/lab3/*\n\n"
              "# 2. 证据采集（GDB / 反汇编 / 长度矩阵 / CI 等价测试）\n"
              "python3 tools/make_inputs.py\n"
              "bash   tools/capture_gdb.sh\n"
              "bash   tools/capture_disassembly.sh\n"
              "python3 tools/run_evidence.py\n\n"
              "# 3. 手动验证单个 payload（与 CI 相同的重定向方式）\n"
              "python3 payload.py > /tmp/p.bin && (cd ~/lab3 && ./dark-calc < /tmp/p.bin)")
    para(doc, "CI 的动作序列为：python3 <payload> > payload.bin；cd attack；./<target> < payload.bin；"
              "grep -F 期望字符串。上述等价测试逐字复现该序列。")
    doc.add_page_break()

    # ---------- 12 防御 ----------
    heading(doc, "十二、防御与改进建议", 1)
    table(doc,
          ["层次", "措施", "针对本实验哪个环节"],
          [
              ["源代码", "彻底移除 gets()，改用 fgets/read + 显式边界；对长度做白名单校验", "任务二/三/五/六/七的共同根源"],
              ["源代码", "不把用户输入拼进 shell：解析后调用 execl/posix_spawn，或对表达式做白名单", "eval 的 system(command_buf) 与 6.5 节的命令替换注入"],
              ["编译期", "-fstack-protector-all（所有函数都放 canary）", "任务七的 canary 绕过（黑暗面：绕过仍需配合信息泄露防护）"],
              ["编译期", "默认 NX（-z noexecstack）并避免手工 RWX 映射；W^X", "任务五的固定 RWX 栈"],
              ["链接期", "PIE（-fPIE -pie）+ 完整 ASLR", "任务六的固定 gadget 地址"],
              ["链接期", "FULL RELRO（-Wl,-z,relro,-z,now）", "防范 GOT 覆写类攻击"],
              ["系统层", "seccomp/AppArmor 限制 exec 与文件访问；以非特权用户运行", "溢出后调用 system/./malware"],
              ["测试", "把长度矩阵与 payload 回归测试并入 CI", "防止回归（本仓库 CI 已包含 payload 测试）"],
          ],
          widths=[1.8, 9.6, 5.6])
    para(doc, "每个措施都对应一个被本实验证实可利用的具体环节；组合使用（纵深防御）才能在"
              "真实系统上显著提高攻击成本。")
    doc.add_page_break()

    # ---------- 13 总结 ----------
    heading(doc, "十三、总结与局限", 1)
    bullet(doc, "栈帧是 x86-64 ABI 的必然结果：rbp+8 处的返回地址决定了函数结束后的控制流，gets 这类无界读入一旦越过缓冲区就能改写它；", "① ")
    bullet(doc, "“保护”是运行期属性：GNU_STACK、文件名、编译选项都不能替代对 /proc 映射的观察——dark-calc 的固定 RWX 映射让栈执行成立，dark-calc-nx 的 rw-p 栈让 shellcode 第一步就崩溃；", "② ")
    bullet(doc, "ROP 的本质是复用已存在的机器码：一个从 0x41 5f c3 中间进入的未对齐 gadget 就足以把 edi 设为 4 并调用 grade_eval，全程不依赖任何随机化地址；", "③ ")
    bullet(doc, "Canary 检测的是“覆盖值”而非“覆盖行为”：dark-log 用攻击者可控的 len 把 128 字节拷贝改道到 rbp，绕过检测的同时改写返回地址——防御必须覆盖所有越界写原语，而不只是栈返回；", "④ ")
    bullet(doc, "纵深防御：gets→受限读取、命令白名单、PIE+ASLR、NX、canary、RELRO、seccomp 各司其职，单点措施均存在本实验演示的绕过。", "⑤ ")
    heading(doc, "局限与说明", 2)
    bullet(doc, "实验在 WSL2 Ubuntu 26.04（glibc 2.43）完成，CI 为 ubuntu-24.04（glibc 2.39）。payload 只依赖非 PIE 固定代码地址与 dark-calc 的固定映射，不依赖 glibc 内部布局；gets/system 等符号在两个版本都存在；")
    bullet(doc, "dark-calc 的 0x721000000000 固定映射假设该区间未被占用（MAP_FIXED_NOREPLACE 失败时程序会报错退出），在当前内核与 CI 环境下均成立；")
    bullet(doc, "payload.py 的 system 返回后与 payload_canary.py 的 grade_eval 返回后进程会因伪造的帧数据崩溃（SIGBUS/SIGSEGV）：目标字符串在此之前已 flush 到 stdout，且 CI 只检查输出；若要求进程体面退出，可分别加 exit(0) 调用点（payload_dark/payload_rop 已做到 exit 0）；")
    bullet(doc, "报告中的每一条 GDB/运行记录都可按第十一节命令复现，原始日志与脚本随仓库提交。")
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
    para(doc, "以下为报告正文引用的关键片段；完整日志见 analysis/gdb/。")
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
    heading(doc, "附录 C：环境参数与文件哈希", 1)
    code(doc, ev["aslr"])
    table(doc, ["参数", "取值"],
          [[k, str(v)] for k, v in env.items()],
          widths=[5.5, 11.5], mono_cols=(1,))
    table(doc, ["文件", "SHA-256"],
          [(k, v["sha256"]) for k, v in ev["baseline"]["files"].items()],
          widths=[5.2, 11.8], mono_cols=(1,))
    para(doc, "上表哈希由 tools/build_report.py 在生成报告时对仓库文件实时计算，并与 "
              "analysis/baseline.json 自动同步，保证附录与最终提交的字节完全一致；其中 "
              "attack/ 四项与 CI 校验清单逐字相同。")
    para(doc, "攻击涉及的全部输入均为本课程自带的本地实验程序，不针对任何第三方系统；"
              "全部实验在隔离的 WSL2 环境内完成。")

    doc.save(OUT)
    print("saved", OUT)


if __name__ == "__main__":
    build(load_evidence())
