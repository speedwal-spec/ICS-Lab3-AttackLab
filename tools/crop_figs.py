#!/usr/bin/env python3
"""Trim the empty black canvas around the terminal captures in analysis/figs.

The evidence screenshots are real captures, but the terminal window is much
taller than the recorded output, so each PNG carries a large empty black area
that turns into wasted white space in the report.  This trims the uniform
background border (keeping a small margin) and leaves the pixels of the capture
itself untouched, so the figures stay honest screenshots.

Usage: python3 tools/crop_figs.py [--dry-run]
"""
from __future__ import annotations

import os
import sys

from PIL import Image, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGS = os.path.join(ROOT, "analysis", "figs")
MARGIN = 10          # px of background kept around the content
TOLERANCE = 6        # colour distance still counted as background


def content_bbox(img):
    """Bounding box of everything that differs from the top-left corner colour."""
    rgb = img.convert("RGB")
    bg = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
    diff = ImageChops.difference(rgb, bg).convert("L")
    mask = diff.point(lambda v: 255 if v > TOLERANCE else 0)
    return mask.getbbox()


def crop(path, dry_run):
    img = Image.open(path)
    box = content_bbox(img)
    if box is None:
        print(f"{os.path.basename(path):24s} uniform image, skipped")
        return
    left, top, right, bottom = box
    left = max(0, left - MARGIN)
    top = max(0, top - MARGIN)
    right = min(img.width, right + MARGIN)
    bottom = min(img.height, bottom + MARGIN)
    new = (left, top, right, bottom)
    if new == (0, 0, img.width, img.height):
        print(f"{os.path.basename(path):24s} already tight, skipped")
        return
    print(f"{os.path.basename(path):24s} {img.width}x{img.height} -> "
          f"{right - left}x{bottom - top}")
    if not dry_run:
        img.crop(new).save(path, optimize=True)


def main():
    dry_run = "--dry-run" in sys.argv[1:]
    for name in sorted(os.listdir(FIGS)):
        if name.startswith("fig_") and name.endswith(".png"):
            crop(os.path.join(FIGS, name), dry_run)


if __name__ == "__main__":
    main()
