#!/usr/bin/env python3
"""Draw the report figures with Pillow (bundled) into analysis/figs/."""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGS = os.path.join(ROOT, "analysis", "figs")
os.makedirs(FIGS, exist_ok=True)

FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "C:/Windows/Fonts/arial.ttf",
]
FONT_BOLD_CANDIDATES = [
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/msyh.ttc",
]


def load_font(paths, size):
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


WHITE = (255, 255, 255)
INK = (0x21, 0x26, 0x30)
GRAY = (0x60, 0x66, 0x72)
BLUE = (0xD6, 0xE4, 0xF7)
BLUE_EDGE = (0x3B, 0x71, 0xB0)
GREEN = (0xD9, 0xEF, 0xDA)
GREEN_EDGE = (0x2E, 0x7D, 0x32)
RED = (0xF8, 0xDC, 0xDC)
RED_EDGE = (0xB0, 0x3A, 0x3A)
YELLOW = (0xFD, 0xF3, 0xC8)
YELLOW_EDGE = (0xA8, 0x7A, 0x1E)
PURPLE = (0xEA, 0xDF, 0xF5)
PURPLE_EDGE = (0x6D, 0x3F, 0x9E)


class Canvas:
    def __init__(self, w, h, title=None):
        self.img = Image.new("RGB", (w, h), WHITE)
        self.d = ImageDraw.Draw(self.img)
        self.f_title = load_font(FONT_BOLD_CANDIDATES, 40)
        self.f = load_font(FONT_CANDIDATES, 26)
        self.f_small = load_font(FONT_CANDIDATES, 22)
        self.f_mono = load_font(FONT_CANDIDATES, 22)
        if title:
            self.d.text((40, 28), title, fill=INK, font=self.f_title)

    def box(self, x, y, w, h, text, fill=BLUE, edge=BLUE_EDGE, font=None,
            align="center", text_color=INK):
        font = font or self.f
        self.d.rounded_rectangle([x, y, x + w, y + h], radius=6,
                                 fill=fill, outline=edge, width=2)
        lines = text.split("\n")
        lh = font.size + 8
        total = lh * len(lines)
        ty = y + (h - total) / 2
        for i, line in enumerate(lines):
            if align == "center":
                tw = self.d.textlength(line, font=font)
                tx = x + (w - tw) / 2
            else:
                tx = x + 10
            self.d.text((tx, ty + i * lh), line, fill=text_color, font=font)
        return self

    def text(self, x, y, s, font=None, color=INK):
        self.d.text((x, y), s, fill=color, font=font or self.f)
        return self

    def text_r(self, x, y, s, font=None, color=INK):
        """Right-anchored text at x."""
        font = font or self.f
        tw = self.d.textlength(s, font=font)
        self.d.text((x - tw, y), s, fill=color, font=font)
        return self

    def arrow(self, x1, y1, x2, y2, color=INK, width=3):
        self.d.line([x1, y1, x2, y2], fill=color, width=width)
        import math
        ang = math.atan2(y2 - y1, x2 - x1)
        head = 14
        for da in (math.pi * 0.85, -math.pi * 0.85):
            self.d.line([x2, y2,
                         x2 + head * math.cos(ang + da),
                         y2 + head * math.sin(ang + da)],
                        fill=color, width=width)
        return self

    def save(self, name):
        self.img.save(os.path.join(FIGS, name))
        print("wrote", os.path.join(FIGS, name))


def fig_frame_input():
    c = Canvas(1500, 1180, "图 1  dark-calc 的 input() 栈帧（固定栈，地址恒定）")
    x0, w = 90, 660
    xa = x0 + w + 40
    rows = [
        ("0x721000801000  守卫页  PROT_NONE", RED, RED_EDGE, "越界写到这里 → SIGSEGV"),
        ("0x721000800ff8  __wrap_main 的返回地址 = 0x401c1f", BLUE, BLUE_EDGE, "main 的调用者"),
        ("0x721000800ff0  main 的 saved rbp = 0", BLUE, BLUE_EDGE, "main 帧"),
        ("0x721000800fe8  input 的返回地址 = 0x401ad1", YELLOW, YELLOW_EDGE,
         "偏移 +24：控制流目标（可被覆盖）"),
        ("0x721000800fe0  input 的 saved rbp = 0x721000800ff0", BLUE, BLUE_EDGE,
         "偏移 +16：可被覆盖"),
        ("0x721000800fd0  expression[16]（gets 写入起点）", GREEN, GREEN_EDGE,
         "偏移 +0：缓冲区"),
    ]
    top = 140
    h = 120
    gap = 16
    y = top
    positions = []
    for label, fill, edge, note in rows:
        c.box(x0, y, w, h, label, fill=fill, edge=edge)
        c.text(xa, y + h / 2 - 30, note, font=c.f_small)
        positions.append((y + h / 2, label))
        y += h + gap
    # overflow arrow on the left
    ay1 = top + len(rows) * (h + gap) - gap / 2
    ay0 = ay1 - (len(rows) - 1) * (h + gap)
    c.arrow(x0 - 70, ay1 + 20, x0 - 70, ay0 - 20, color=RED_EDGE, width=4)
    c.text(12, (ay0 + ay1) / 2 - 60, "gets 溢出\n方向（地址增大）",
           font=c.f_small, color=RED_EDGE)
    c.text(x0, 970, "缓冲到返回地址：24 字节", font=c.f_small)
    c.text(x0, 1010, "缓冲到守卫页：48 字节（单次输入上限 47 字节）", font=c.f_small)
    c.text(x0, 1050, "leave = mov rsp,rbp; pop rbp；ret = 从 rsp 弹出下一条指令地址 —— 因此覆盖返回地址即可劫持控制流。",
           font=c.f_small, color=GRAY)
    c.save("fig_frame_input.png")


def fig_fixed_stack():
    c = Canvas(1500, 800, "图 2  dark-calc 的固定栈映射（/proc 映射与 GDB 观察）")
    y0 = 160
    bar_h = 150
    margin = 90
    # total span: 0x721000000000 .. 0x721000802000 (0x802000 bytes)
    total = 0x802000
    xs = margin
    xe = 1500 - margin
    span = xe - xs
    parts = [
        (0x0000, 0x1000, RED, RED_EDGE, "0x721000000000\n---p 守卫页（PROT_NONE）"),
        (0x1000, 0x801000, GREEN, GREEN_EDGE,
         "0x721000001000 – 0x721000801000   rwxp 固定栈（8 MiB，可读可写可执行）"),
        (0x801000, 0x802000, RED, RED_EDGE, "0x721000801000\n---p 守卫页（PROT_NONE）"),
    ]
    for lo, hi, fill, edge, label in parts:
        x1 = xs + span * lo / total
        x2 = xs + span * hi / total
        c.box(int(x1), y0, int(x2 - x1), bar_h, label, fill=fill, edge=edge)
    # markers
    def marker(addr, color, label, below=True):
        x = xs + span * (addr - 0x721000000000) / total
        yy = y0 + bar_h + 24 if below else y0 - 24
        c.d.line([x, y0 - 18, x, y0 + bar_h + 18], fill=color, width=3)
        font = c.f_small
        tw = c.d.textlength(label, font=font)
        if x + tw + 10 > 1500:
            c.text_r(x - 8, yy, label, font=font, color=color)
        else:
            c.text(x + 8, yy, label, font=font, color=color)
    marker(0x721000801000, RED_EDGE, "fixed_stack_top = 0x721000801000（__wrap_main 把 rsp 设到这里）")
    marker(0x721000800fd0, INK, "input() 缓冲区 0x721000800fd0（确定性地址）")
    c.text(90, y0 + bar_h + 120, "mmap(0x721000000000, 0x802000, RWX, MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE, -1, 0)；",
           font=c.f_small)
    c.text(90, y0 + bar_h + 156, "两端各 mprotect 0x1000 为 PROT_NONE。地址固定 ⇒ 不受 ASLR 影响，且栈页可执行。",
           font=c.f_small)
    c.save("fig_fixed_stack.png")


def payload_strip(c, title, x, y, w, cells, note):
    c.text(x, y, title, font=c.f, color=INK)
    total = sum(sz for _, sz, _, _ in cells)
    scale = w / total
    xc = x
    for text, sz, fill, edge in cells:
        cw = sz * scale
        c.box(int(xc), y + 40, int(cw) - 2, 54, text, fill=fill, edge=edge,
              font=c.f_small)
        xc += cw
    c.text(x, y + 100, note, font=c.f_small, color=GRAY)


def fig_payloads():
    c = Canvas(1500, 1560, "图 3  四个 payload 的字节布局")
    x, w = 90, 1320
    payload_strip(c, "payload.py（32 字节，dark-calc → system(\"./malware\")）", x, 130, w,
                  [('"./malware\\0"+"A"*6', 16, GREEN, GREEN_EDGE),
                   ('"B" x 8', 8, BLUE, BLUE_EDGE),
                   ("0x401a6b", 8, YELLOW, YELLOW_EDGE)],
                  "偏移 0–15：command_buf 的字符串（strcpy 到第 1 个 NUL 为止）；偏移 16–23：saved rbp（伪造）；偏移 24–31：返回地址 → eval 的 mov edi,0x6030d0; call system@plt")
    payload_strip(c, "payload_dark.py（40 字节，dark-calc → 固定栈 shellcode）", x, 340, w,
                  [("push4/pop rdi/movabs/jmp（15 B）", 15, GREEN, GREEN_EDGE),
                   ("NOP x 9", 9, GRAY, GRAY),
                   ("0x721000800fd0", 8, YELLOW, YELLOW_EDGE),
                   ("0x4019b9", 8, PURPLE, PURPLE_EDGE)],
                  "偏移 24：返回地址 → 缓冲区本身（栈页 rwxp）；偏移 32：grade_eval 返回后落到 mov edi,0; call exit@plt，进程 exit(0)")
    payload_strip(c, "payload_rop.py（56 字节，dark-calc-nx → ROP）", x, 550, w,
                  [('"R" x 24', 24, BLUE, BLUE_EDGE),
                   ("0x401a33", 8, YELLOW, YELLOW_EDGE),
                   ("4", 8, GREEN, GREEN_EDGE),
                   ("0x401978", 8, PURPLE, PURPLE_EDGE),
                   ("0x4018aa", 8, PURPLE, PURPLE_EDGE)],
                  "pop rdi; ret（csu 尾部 41 5f c3 的第二字节）→ 参数 4 → grade_eval(4) → mov edi,0; call exit@plt（exit(0)）")
    payload_strip(c, "payload_canary.py（260 字节，dark-log → 保 canary 改返回地址）", x, 760, w,
                  [('"K" x 8', 8, BLUE, BLUE_EDGE),
                   ("0x4018a3", 8, YELLOW, YELLOW_EDGE),
                   ("4", 8, GREEN, GREEN_EDGE),
                   ("0x401677", 8, PURPLE, PURPLE_EDGE),
                   ('"L" x 224', 224, GRAY, GRAY),
                   ("len=0xa0", 4, RED, RED_EDGE)],
                  "偏移 0–127 是 memcpy 的源：伪造 saved rbp + ROP 链；偏移 256–259 把 len 设成 160，使 memcpy 目的 = rbp；canary（偏移 280）未被触碰")
    c.save("fig_payloads.png")


def fig_darklog():
    c = Canvas(1500, 1000, "图 4  dark-log：用 len 控制的 memcpy 绕过栈 canary")
    x0, w = 90, 680
    top = 130
    h = 54
    gap = 10
    slots = [
        ("rbp+0x10  main 帧（拷贝区间之外）", BLUE, BLUE_EDGE),
        ("rbp+0x08  返回地址 → 0x4018a3（pop rdi; ret）", YELLOW, YELLOW_EDGE),
        ("rbp+0x00  saved rbp → \"KKKKKKKK\"", YELLOW, YELLOW_EDGE),
        ("rbp-0x08  stack canary（保持原值，校验通过）", GREEN, GREEN_EDGE),
        ("rbp-0x18  pad[8]（gets 的 NUL 落在这里）", BLUE, BLUE_EDGE),
        ("rbp-0x20  len = 0xa0（由输入偏移 256 控制）", RED, RED_EDGE),
        ("rbp-0xa0  logMsg[128]（memcpy 目的基址）", BLUE, BLUE_EDGE),
        ("rbp-0x120 expression[128]（gets 写入点 / memcpy 源）", GREEN, GREEN_EDGE),
    ]
    y = top
    for label, fill, edge in slots:
        c.box(x0, y, w, h, label, fill=fill, edge=edge)
        y += h + gap
    xa = x0 + w + 60
    c.text(xa, 150, "memcpy(logMsg + len, expression, 128)", font=c.f, color=INK)
    c.text(xa, 200, "len = 160 ⇒ 目的地址 = rbp + 0", font=c.f_small, color=RED_EDGE)
    c.arrow(xa + 40, 280, xa + 40, 500, color=RED_EDGE, width=4)
    c.text(xa + 70, 320, "128 字节拷贝覆盖", font=c.f_small, color=RED_EDGE)
    c.text(xa + 70, 358, "saved rbp + 返回地址", font=c.f_small, color=RED_EDGE)
    c.text(xa + 70, 410, "canary 在 rbp-8", font=c.f_small, color=INK)
    c.text(xa + 70, 448, "拷贝区间 rbp..rbp+0x7f", font=c.f_small, color=INK)
    c.text(xa + 70, 486, "⇒ 校验自然通过", font=c.f_small, color=GREEN_EDGE)
    c.text(xa, 570, "输入只有 260 字节：gets 的 NUL 落在偏移 260", font=c.f_small)
    c.text(xa, 608, "（pad 区），canary 在偏移 280，没有被覆盖。", font=c.f_small)
    c.text(xa, 660, "返回地址被改成 ROP 链：", font=c.f_small)
    c.text(xa, 698, "pop rdi; ret → 4 → grade_eval(4)", font=c.f_small)
    c.save("fig_darklog.png")


def fig_proc_tree():
    c = Canvas(1500, 820, "图 5  payload.py 的运行现场：malware 沿父链找到 dark-calc")
    cx = 750
    c.box(cx - 190, 140, 380, 90, "dark-calc\n（被利用进程）", fill=GREEN, edge=GREEN_EDGE)
    c.box(cx - 190, 330, 380, 90, "sh -c ./malware\n（由 system() 启动）", fill=BLUE, edge=BLUE_EDGE)
    c.box(cx - 190, 520, 380, 90, "malware（shell 脚本）\n沿父链向上找\ncomm == dark-calc", fill=YELLOW, edge=YELLOW_EDGE)
    c.arrow(cx, 230, cx, 330)
    c.arrow(cx, 420, cx, 520)
    c.box(cx + 300, 330, 420, 150,
          "逐级 ps -o ppid= / ps -o comm=\nsh → dark-calc：命中！\n打印成功横幅：\n### You have successfully\ndetonated the bomb! ###",
          fill=WHITE, edge=GRAY)
    c.arrow(cx + 190, 375, cx + 300, 405)
    c.text(90, 700, "实测进程树（analysis/logs/ci_simulation.txt）：dark-calc → sh -c -- ./malware → malware（pstree 输出），判定成功。",
           font=c.f_small, color=GRAY)
    c.save("fig_proc_tree.png")


def main():
    fig_frame_input()
    fig_fixed_stack()
    fig_payloads()
    fig_darklog()
    fig_proc_tree()


if __name__ == "__main__":
    main()
