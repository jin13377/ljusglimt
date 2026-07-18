#!/usr/bin/env python3
"""Create deterministic, local SVG illustrations for public news articles.

The generator is deliberately offline and standard-library only. It never
places source text, people, logos or documentary details in an image. The same
article fingerprint always produces the same safe abstract illustration.

Style: handmade Scandinavian paper collage. Each illustration is built from
torn coloured paper, felt, fabric, embroidered details and soft layered
shapes with visible fibres and discreet shadows. No text, logos, real people
or exact event imagery.
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
STYLE_VERSION = "glimt-paper-collage-v1"
HEX_20_RE = re.compile(r"^[0-9a-f]{20}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IMAGE_KEYS = {
    "url", "alt", "style_version", "source_fingerprint",
    "width", "height", "sha256",
}


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


# Torn-paper palette per category. Each entry is a list of
# (paper, felt, fabric, thread) colours used for that category's collage.
CATEGORY_PALETTE = {
    "Natur": ("#1f6f52", "#3fa66b", "#bfe3c8", "#0c3a25"),
    "Teknik": ("#26405e", "#3f78a8", "#cfe3f4", "#13283f"),
    "Halsa": ("#9c2f4a", "#e07a94", "#fbd9e1", "#5e132b"),
    "Manniskor": ("#b5651e", "#e0a35b", "#f6e0c8", "#6e3a12"),
    "Djur": ("#2f5d3a", "#6aa55f", "#dff0cf", "#163a20"),
    "Samhalle": ("#3a3f7a", "#6f74c2", "#d9def0", "#1f2456"),
}
DEFAULT_PALETTE = ("#43506b", "#7a8aa0", "#e3e9f0", "#232b3f")


def _drop_shadow_filter() -> str:
    return (
        '<filter id="ds" x="-20%" y="-20%" width="140%" height="140%">'
        '<feDropShadow dx="0" dy="10" stdDeviation="10" flood-color="#000000" flood-opacity="0.18"/>'
        '</filter>'
    )


def _torn_paper(seed: bytes, index: int, paper: str, x: float, y: float,
               width: float, height: float, rotate: float,
               stitch: str | None = None) -> str:
    # Build a ragged torn edge: many short segments with pseudo-random jitter,
    # so the paper looks hand-ripped rather than cut.
    jitter = seed[(index * 5) % len(seed)]
    seg = 9
    pts = []

    def j(base: float, k: int, amp: int) -> float:
        return base + (((seed[(index * 3 + k) % len(seed)] % (2 * amp + 1)) - amp))

    top = y
    bottom = y + height
    left = x
    right = x + width
    for t in range(seg + 1):
        f = t / seg
        px = left + (right - left) * f + j(0, t, 9)
        py = top + j(0, t + 1, 7) if t not in (0, seg) else top
        pts.append((round(px, 1), round(py, 1)))
    for t in range(seg + 1):
        f = t / seg
        px = right - (right - left) * f + j(0, t + 20, 9)
        py = bottom - j(0, t + 21, 7) if t not in (0, seg) else bottom
        pts.append((round(px, 1), round(py, 1)))
    for t in range(seg + 1):
        f = t / seg
        px = right - (right - left) * f
        py = bottom - (bottom - top) * f + j(0, t + 40, 9)
        pts.append((round(px, 1), round(py, 1)))
    for t in range(seg + 1):
        f = t / seg
        px = left + (right - left) * f
        py = top + (bottom - top) * f - j(0, t + 60, 9)
        pts.append((round(px, 1), round(py, 1)))
    points = " ".join(f"{a} {b}" for a, b in pts)
    cx = x + width / 2
    cy = y + height / 2
    stroke = f' stroke="{stitch}" stroke-width="2.4" stroke-dasharray="2 6" stroke-linecap="round"' if stitch else ""
    return f'<polygon points="{points}" fill="{paper}"{stroke} transform="rotate({rotate:.1f} {cx:.1f} {cy:.1f})"/>'


def _soft_blob(seed: bytes, index: int, color: str, cx: float, cy: float, r: float, opacity: float) -> str:
    # A fuzzy felt-like blob built from a wobbly circle path.
    step = 14
    coords = []
    for k in range(step):
        ang = (k / step) * 6.283185
        rr = r * (0.82 + (seed[(index * 4 + k) % len(seed)] % 36) / 100)
        coords.append((cx + rr * 0.92 * pow(-1, 0) * __import__("math").cos(ang),
                       cy + rr * __import__("math").sin(ang)))
    d = "M" + " L".join(f"{a:.0f} {b:.0f}" for a, b in coords) + " Z"
    return f'<path d="{d}" fill="{color}" opacity="{opacity:.2f}"/>'


def _category_motif(seed: bytes, category: str, accent: str, thread: str) -> str:
    variant = seed[4] % 6
    marker = f'data-collage-motif="{category.lower()}"'
    if category == "Natur":
        # A leaf/stem motif built from felt and embroidered vein.
        return (
            f'<g {marker}>'
            f'<path d="M640 660 C520 560 520 380 640 250 C760 380 760 560 640 660 Z" fill="{accent}" opacity="0.82"/>'
            f'<path d="M640 650 V280" stroke="{thread}" stroke-width="6" fill="none" stroke-linecap="round"/>'
            f'<path d="M640 470 C600 450 575 430 552 405 M640 540 C684 520 709 500 732 475" stroke="{thread}" stroke-width="4" fill="none" stroke-linecap="round" opacity="0.8"/>'
            '</g>'
        )
    if category == "Teknik":
        # Circuit-like embroidered lines with node dots.
        return (
            f'<g {marker}>'
            f'<path d="M430 430 H610 V300 H820" stroke="{thread}" stroke-width="7" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<circle cx="430" cy="430" r="16" fill="{accent}"/>'
            f'<circle cx="610" cy="300" r="16" fill="{accent}"/>'
            f'<circle cx="820" cy="300" r="16" fill="{accent}"/>'
            f'<rect x="470" y="500" width="120" height="80" rx="12" fill="{accent}" opacity="0.78"/>'
            '</g>'
        )
    if category == "Halsa":
        # A calm heartbeat / pulse stitched line.
        return (
            f'<g {marker}>'
            f'<path d="M400 440 H560 L600 320 L660 560 L700 440 H880" stroke="{thread}" stroke-width="9" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<circle cx="640" cy="440" r="40" fill="{accent}" opacity="0.8"/>'
            '</g>'
        )
    if category == "Manniskor":
        # Overlapping friendly figures from torn fabric, no faces.
        return (
            f'<g {marker}>'
            f'<circle cx="560" cy="380" r="46" fill="{accent}"/>'
            f'<path d="M512 600 C512 500 608 500 608 600 Z" fill="{accent}" opacity="0.82"/>'
            f'<circle cx="720" cy="408" r="40" fill="{thread}"/>'
            f'<path d="M680 600 C680 512 760 512 760 600 Z" fill="{thread}" opacity="0.82"/>'
            '</g>'
        )
    if category == "Djur":
        # A soft paw / ear motif in felt.
        return (
            f'<g {marker}>'
            f'<path d="M640 620 C520 560 520 400 640 300 C760 400 760 560 640 620 Z" fill="{accent}" opacity="0.82"/>'
            f'<circle cx="592" cy="360" r="34" fill="{thread}"/>'
            f'<circle cx="688" cy="360" r="34" fill="{thread}"/>'
            f'<path d="M640 392 C612 392 600 416 612 436 H668 C680 416 668 392 640 392 Z" fill="{thread}"/>'
            '</g>'
        )
    # Samhalle and default: linked community dots with stitched threads.
    return (
        f'<g {marker}>'
        f'<circle cx="540" cy="420" r="40" fill="{accent}"/>'
        f'<circle cx="740" cy="400" r="34" fill="{accent}" opacity="0.86"/>'
        f'<circle cx="650" cy="560" r="30" fill="{accent}" opacity="0.8"/>'
        f'<path d="M540 420 L740 400 L650 560 Z" stroke="{thread}" stroke-width="6" fill="none" stroke-linejoin="round"/>'
        '</g>'
    )


def render_svg(item: dict) -> bytes:
    article_id = str(item["id"])
    fingerprint = str(item["source_fingerprint"])
    category = str(item.get("category") or "Samhalle").strip() or "Samhalle"
    seed = hashlib.sha256(f"{article_id}:{fingerprint}:{STYLE_VERSION}".encode()).digest()
    palette = CATEGORY_PALETTE.get(category, DEFAULT_PALETTE)
    paper, felt, fabric, thread = palette
    # A warm off-white base that reads as a craft table / backing sheet.
    base = "#f3ece1"
    # Three overlapping torn scraps (paper, felt, fabric) inset from the edges
    # so their ragged borders are visible, each with a soft drop shadow.
    scrap1 = _torn_paper(seed, 0, fabric, 70, 60, 640, 470, -3.5, stitch=thread)
    scrap2 = _torn_paper(seed, 1, felt, 560, 240, 660, 520, 4.0, stitch=thread)
    scrap3 = _torn_paper(seed, 2, paper, 360, 380, 560, 400, -1.5, stitch=thread)
    # Fuzzy felt blobs for soft layered texture.
    blobs = []
    for index in range(5):
        offset = 4 + index * 3
        bx = 120 + int(seed[offset] / 255 * 1040)
        by = 110 + int(seed[offset + 1] / 255 * 640)
        br = 90 + int(seed[offset + 2] / 255 * 150)
        blobs.append(_soft_blob(seed, index, felt if index % 2 else fabric, bx, by, br, 0.16))
    # Fibre speckle on top for visible paper grain.
    fibres = "".join(
        f'<circle cx="{120 + (seed[i % len(seed)] % 1040):.0f}" cy="{120 + (seed[(i + 1) % len(seed)] % 600):.0f}" r="1.4" fill="{thread}" opacity="0.25"/>'
        for i in range(36)
    )
    motif = _category_motif(seed, category, felt, thread)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
<defs>
  <filter id="ds" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="10" stdDeviation="10" flood-color="#000000" flood-opacity="0.18"/></filter>
  <filter id="fibre"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" result="n"/><feColorMatrix in="n" type="saturate" values="0"/><feComponentTransfer><feFuncA type="linear" slope="0.05"/></feComponentTransfer><feComposite operator="in" in2="SourceGraphic"/></filter>
</defs>
<rect width="{WIDTH}" height="{HEIGHT}" fill="{base}"/>
<g filter="url(#ds)">
{scrap1}
{scrap2}
{scrap3}
</g>
{''.join(blobs)}
<g filter="url(#fibre)" opacity="0.6"><rect width="{WIDTH}" height="{HEIGHT}" fill="{thread}"/></g>
{fibres}
{motif}
<g fill="{felt}" opacity="0.9"><circle cx="104" cy="106" r="8"/><circle cx="130" cy="106" r="8"/><circle cx="156" cy="106" r="8"/></g>
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
        if (not isinstance(item, dict) or item.get("public_eligible") is not True
                or item.get("source_image_verified") is True):
            if isinstance(item, dict) and item.get("source_image_verified") is True:
                item.pop("generated_image", None)
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
    print(f"Free visuals: {created} created, {reused} reused, {skipped} ineligible or source-backed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
