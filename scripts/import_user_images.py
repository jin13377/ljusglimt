#!/usr/bin/env python3
"""Import Daniel's own images into the Ljusglimt user-image fallback library.

Copies images from the source desktop folder, converts png/jpg/heic to WebP
at 1280x848, and writes a stable slug per file. Non-destructive: never
overwrites news.json; only populates public/news-images/user/*.webp.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Pillow missing", file=sys.stderr)
    raise

SOURCE_DIR = Path("C:/Users/danie/Desktop/Ljusglimt")
OUT_DIR = Path(__file__).resolve().parents[1] / "public/news-images/user"
ACCEPTED = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".bmp", ".tif", ".tiff"}
TARGET = (1280, 848)


def slugify(name: str) -> str:
    stem = Path(name).stem.lower()
    stem = re.sub(r"[^a-z0-9]+", "-", stem)
    stem = re.sub(r"-{2,}", "-", stem).strip("-")
    return stem or "image"


def convert_one(src: Path, dst: Path) -> None:
    im = Image.open(src)
    if im.mode in ("RGBA", "P", "LA"):
        im = im.convert("RGB")
    else:
        im = im.convert("RGB")
    im.thumbnail(TARGET, Image.LANCZOS)
    canvas = Image.new("RGB", TARGET, (255, 255, 255))
    offset = ((TARGET[0] - im.width) // 2, (TARGET[1] - im.height) // 2)
    canvas.paste(im, offset)
    canvas.save(dst, "WEBP", quality=90, method=6)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in SOURCE_DIR.iterdir() if p.suffix.lower() in ACCEPTED)
    used: dict[str, int] = {}
    count = 0
    for src in files:
        base = slugify(src.name)
        if base in used:
            used[base] += 1
            base = f"{base}-{used[base]}"
        else:
            used[base] = 0
        dst = OUT_DIR / f"{base}.webp"
        convert_one(src, dst)
        count += 1
        print(f"imported {src.name} -> {dst.name}")
    print(f"Done: {count} images in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
