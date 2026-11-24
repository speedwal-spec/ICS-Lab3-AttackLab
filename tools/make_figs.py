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

    def _fit(self, paths, size, text, maxw, min_size=13):
        """Largest font size (<= size) at which every line fits in maxw."""
        while size > min_size:
            font = load_font(paths, size)
            widest = max(self.d.textlength(line, font=font)
                         for line in text.split("\n"))
            if widest <= maxw:
                return font
            size -= 1
        return load_font(paths, min_size)

    def box(self, x, y, w, h, text, fill=BLUE, edge=BLUE_EDGE, font=None,
            align="center", text_color=INK):
        if font is None:
            # Long labels shrink until they fit both the width and the height,
            # instead of spilling over the border.
            font = self._fit(FONT_CANDIDATES, 26, text, w - 24)
            while font.size > 12 and (font.size + 8) * len(text.split("\n")) > h - 12:
                font = load_font(FONT_CANDIDATES, font.size - 1)
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
    c = Canvas(1500, 1180, "dark-calc 的 input() 栈帧（固定栈，地址恒定）")
    x0, w = 90, 660
    xa = x0 + w + 40
    rows = [
        ("0x721000801000  守卫页  PROT_NONE", RED, RED_EDGE, "越界写到这里 → SIGSEGV"),
        ("0x721000800ff8  __wrap_main 的返回地址 = 0x401c1f", BLUE, BLUE_EDGE, "main 的调用者"),
        ("0x721000800ff0  main 的 saved rbp（非 0，随 ASLR 变化）", BLUE, BLUE_EDGE, "main 帧"),
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
    """Schematic of the fixed mapping: guards are drawn at readable width,
    not to scale (a 4 KiB guard next to 8 MiB is sub-pixel otherwise)."""
    c = Canvas(1500, 760, "dark-calc 的固定栈映射（/proc 映射与 GDB 观察）")
    y0 = 170
    bar_h = 150
    # 0x721000000000 .. 0x721000802000, guards 0x1000 at each end, 8 MiB in between.
    x_guard, x_mid, gap = 150, 980, 14
    x_right = x_guard + x_mid + gap * 2
    c.box(70, y0, x_guard, bar_h,
          "0x721000000000\n---p 守卫页\nPROT_NONE", fill=RED, edge=RED_EDGE)
    c.box(70 + x_guard + gap, y0, x_mid, bar_h,
          "0x721000001000 – 0x721000801000\nrwxp 固定栈（8 MiB，可读可写可执行）",
          fill=GREEN, edge=GREEN_EDGE)
    c.box(70 + x_right, y0, x_guard, bar_h,
          "0x721000801000\n0x721000802000\n---p 守卫页", fill=RED, edge=RED_EDGE)
    mid_left = 70 + x_guard + gap
    mid_right = mid_left + x_mid

    # fixed_stack_top sits at the right edge of the executable region.
    c.d.line([mid_right, y0 - 26, mid_right, y0 + bar_h + 26], fill=RED_EDGE, width=3)
    c.text_r(mid_right - 8, y0 - 64,
             "fixed_stack_top = 0x721000801000（__wrap_main 把 rsp 设到这里）",
             font=c.f_small, color=RED_EDGE)

    # input()'s buffer: near the top of the mapping, ~4 KiB below the guard.
    xb = mid_right - x_mid * 0x1000 / 0x800000
    c.d.line([xb, y0 + bar_h + 22, xb, y0 + bar_h + 70], fill=INK, width=3)
    c.text(mid_left + 16, y0 + bar_h + 78,
           "input() 缓冲区 0x721000800fd0（确定性地址，距守卫页 0x30 字节）",
           font=c.f_small, color=INK)

    c.text(70, y0 + bar_h + 140, "mmap(0x721000000000, 0x802000, RWX, MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE, -1, 0)；",
           font=c.f_small)
    c.text(70, y0 + bar_h + 176, "两端各 mprotect 0x1000 为 PROT_NONE。地址固定 → 不受 ASLR 影响，且栈页可执行。",
           font=c.f_small)
    c.text(70, y0 + bar_h + 212, "（示意图，非等比例：守卫页各 4 KiB，中间 8 MiB。）",
           font=c.f_small, color=GRAY)
    c.save("fig_fixed_stack.png")


def fig_darklog():
    c = Canvas(1500, 1000, "dark-log：用 len 控制的 memcpy 绕过栈 canary")
    x0, w = 90, 680
    top = 130
    h = 54
    gap = 10
    slots = [
        ("rbp+0x10  main 帧（拷贝区间之外）", BLUE, BLUE_EDGE),
        ("rbp+0x08  返回地址 → 0x4018a3（pop rdi; ret）", YELLOW, YELLOW_EDGE),
        ("rbp+0x00  saved rbp → \"KKKKKKKK\"", YELLOW, YELLOW_EDGE),
        ("rbp-0x08  stack canary（保持原值，校验通过）", GREEN, GREEN_EDGE),
        ("rbp-0x1c  pad[8]（gets 的 NUL 落在这里）", BLUE, BLUE_EDGE),
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
    c.text(xa, 200, "len = 160 → 目的地址 = rbp + 0", font=c.f_small, color=RED_EDGE)
    c.arrow(xa + 40, 280, xa + 40, 500, color=RED_EDGE, width=4)
    c.text(xa + 70, 320, "128 字节拷贝覆盖", font=c.f_small, color=RED_EDGE)
    c.text(xa + 70, 358, "saved rbp + 返回地址", font=c.f_small, color=RED_EDGE)
    c.text(xa + 70, 410, "canary 在 rbp-8", font=c.f_small, color=INK)
    c.text(xa + 70, 448, "拷贝区间 rbp..rbp+0x7f", font=c.f_small, color=INK)
    c.text(xa + 70, 486, "→ 校验自然通过", font=c.f_small, color=GREEN_EDGE)
    c.text(xa, 570, "输入只有 260 字节：gets 的 NUL 落在偏移 260", font=c.f_small)
    c.text(xa, 608, "（pad 区），canary 在偏移 280，没有被覆盖。", font=c.f_small)
    c.text(xa, 660, "返回地址被改成 ROP 链：", font=c.f_small)
    c.text(xa, 698, "pop rdi; ret → 4 → ret（垫片）→ grade_eval(4)", font=c.f_small)
    c.save("fig_darklog.png")


def fig_proc_tree():
    c = Canvas(1500, 820, "payload.py 的运行现场：malware 沿父链找到 dark-calc")
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
    fig_darklog()
    fig_proc_tree()


if __name__ == "__main__":
    main()
