#!/usr/bin/env python3
"""Create deterministic, local SVG illustrations for public news articles.

The generator is deliberately offline and standard-library only. It never
places source text, people, logos or documentary details in an image. The same
article fingerprint always produces the same safe abstract illustration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

WIDTH = 1280
HEIGHT = 848
STYLE_VERSION = "glimt-abstract-v1"
HEX_20_RE = re.compile(r"^[0-9a-f]{20}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IMAGE_KEYS = {
    "url", "alt", "style_version", "source_fingerprint",
    "width", "height", "sha256",
}

PALETTES = (
    ("#062f2b", "#0e7467", "#f5c45d", "#d7fff4"),
    ("#102a43", "#286a8d", "#ffb45b", "#e1f4ff"),
    ("#382354", "#7957a8", "#f2b84b", "#f8edff"),
    ("#4a2531", "#a64b60", "#ffc76a", "#fff0f3"),
    ("#17351f", "#3f8450", "#f5d56b", "#e8ffe9"),
    ("#3f2f18", "#a36c2f", "#f6c85f", "#fff6dc"),
    ("#18314c", "#3d78a1", "#7bd8c4", "#eefcff"),
)


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def atomic_json_write(path: Path, document: dict) -> None:
    payload = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    atomic_write(path, payload)


def expected_filename(item: dict) -> str:
    article_id = str(item.get("id") or "")
    fingerprint = str(item.get("source_fingerprint") or "")
    if not HEX_20_RE.fullmatch(article_id) or not HEX_20_RE.fullmatch(fingerprint):
        raise ValueError("article id and source fingerprint must be 20 lowercase hex characters")
    return f"{article_id}-{fingerprint[:8]}-v1.svg"


def _motif(seed: bytes, accent: str, light: str) -> str:
    variant = seed[4] % 4
    if variant == 0:
        return f'''<g fill="none" stroke="{light}" stroke-width="18" opacity=".72">
  <ellipse cx="640" cy="424" rx="238" ry="112" transform="rotate(-18 640 424)"/>
  <ellipse cx="640" cy="424" rx="238" ry="112" transform="rotate(42 640 424)"/>
</g><circle cx="640" cy="424" r="54" fill="{accent}"/>'''
    if variant == 1:
        return f'''<g fill="{light}" opacity=".78">
  <circle cx="535" cy="375" r="66"/><circle cx="744" cy="350" r="52"/><circle cx="672" cy="535" r="72"/>
</g><path d="M535 375 744 350 672 535Z" fill="none" stroke="{accent}" stroke-width="22" stroke-linejoin="round"/>'''
    if variant == 2:
        return f'''<path d="M640 620C470 545 455 342 640 225c185 117 170 320 0 395Z" fill="{light}" opacity=".74"/>
<path d="M640 590V275M640 430c-68-10-114-48-146-102M640 472c76-11 125-56 158-121" fill="none" stroke="{accent}" stroke-width="18" stroke-linecap="round"/>'''
    return f'''<path d="M640 212 684 355l148-36-104 111 104 110-148-35-44 143-44-143-148 35 104-110-104-111 148 36Z" fill="{light}" opacity=".76"/>
<circle cx="640" cy="430" r="78" fill="{accent}"/>'''


def render_svg(item: dict) -> bytes:
    article_id = str(item["id"])
    fingerprint = str(item["source_fingerprint"])
    seed = hashlib.sha256(f"{article_id}:{fingerprint}:{STYLE_VERSION}".encode()).digest()
    dark, middle, accent, light = PALETTES[seed[0] % len(PALETTES)]
    circles = []
    for index in range(7):
        offset = 5 + index * 3
        x = 90 + int(seed[offset] / 255 * 1100)
        y = 80 + int(seed[offset + 1] / 255 * 688)
        radius = 70 + int(seed[offset + 2] / 255 * 190)
        opacity = 0.08 + (seed[(offset + 7) % len(seed)] / 255) * 0.16
        circles.append(f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{light}" opacity="{opacity:.3f}"/>')
    wave_y = 610 + seed[2] % 80
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{dark}"/><stop offset="1" stop-color="{middle}"/></linearGradient>
  <radialGradient id="glow"><stop stop-color="{accent}" stop-opacity=".72"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>
</defs>
<rect width="1280" height="848" fill="url(#bg)"/>
<circle cx="{260 + seed[1] * 2}" cy="{180 + seed[3]}" r="390" fill="url(#glow)"/>
{''.join(circles)}
<path d="M0 {wave_y} C260 {wave_y - 150} 450 {wave_y + 110} 690 {wave_y - 45}S1080 {wave_y - 40} 1280 {wave_y - 130}V848H0Z" fill="{dark}" opacity=".28"/>
{_motif(seed, accent, light)}
<g fill="{accent}" opacity=".9"><circle cx="104" cy="106" r="8"/><circle cx="130" cy="106" r="8"/><circle cx="156" cy="106" r="8"/></g>
</svg>'''
    return svg.encode("utf-8")


def valid_metadata(item: dict, image_path: Path) -> bool:
    image = item.get("generated_image")
    if not isinstance(image, dict) or set(image) != IMAGE_KEYS or not image_path.is_file():
        return False
    payload = image_path.read_bytes()
    return (
        image.get("url") == f"/news-images/generated/{image_path.name}"
        and image.get("alt") == "Automatiskt skapad redaktionell illustration."
        and image.get("style_version") == STYLE_VERSION
        and image.get("source_fingerprint") == item.get("source_fingerprint")
        and image.get("width") == WIDTH
        and image.get("height") == HEIGHT
        and isinstance(image.get("sha256"), str)
        and SHA256_RE.fullmatch(image["sha256"]) is not None
        and hashlib.sha256(payload).hexdigest() == image["sha256"]
        and b"<text" not in payload.lower()
        and b"<script" not in payload.lower()
    )


def process(news_path: Path, output_dir: Path) -> tuple[int, int, int]:
    document = json.loads(news_path.read_text(encoding="utf-8"))
    items = document.get("items")
    if not isinstance(items, list):
        raise ValueError("news document must contain an items list")
    created = reused = skipped = 0
    referenced: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or item.get("public_eligible") is not True:
            skipped += 1
            continue
        filename = expected_filename(item)
        image_path = output_dir / filename
        referenced.add(filename)
        if valid_metadata(item, image_path):
            reused += 1
            continue
        payload = render_svg(item)
        atomic_write(image_path, payload)
        item["generated_image"] = {
            "url": f"/news-images/generated/{filename}",
            "alt": "Automatiskt skapad redaktionell illustration.",
            "style_version": STYLE_VERSION,
            "source_fingerprint": item["source_fingerprint"],
            "width": WIDTH,
            "height": HEIGHT,
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        created += 1
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale in output_dir.glob("*-v1.svg"):
        if stale.name not in referenced and not stale.is_symlink():
            stale.unlink()
    atomic_json_write(news_path, document)
    return created, reused, skipped


def main() -> int:
    base = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--news", type=Path, default=base / "data/news.json")
    parser.add_argument("--output-dir", type=Path, default=base / "public/news-images/generated")
    args = parser.parse_args()
    created, reused, skipped = process(args.news, args.output_dir)
    print(f"Free visuals: {created} created, {reused} reused, {skipped} ineligible.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
