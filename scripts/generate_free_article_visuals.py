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
STYLE_VERSION = "glimt-paper-collage-v2"
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


# Torn-paper palettes per category. Each category has several palettes
# (paper, felt, fabric, thread) chosen by the article seed, so articles in
# the same category get visibly different colourways instead of one repeated
# image. All colours must be valid 6-digit hex.
CATEGORY_PALETTES = {
    "Natur": [
        ("#1f6f52", "#3fa66b", "#bfe3c8", "#0c3a25"),
        ("#2f6b3a", "#7bb36a", "#e3f0cf", "#173a1f"),
        ("#3a7d44", "#a6cf6e", "#dff3c4", "#1f4a26"),
    ],
    "Teknik": [
        ("#26405e", "#3f78a8", "#cfe3f4", "#13283f"),
        ("#2b3a66", "#5a7fd6", "#dbe6ff", "#16213f"),
        ("#1f4a5e", "#3fb0b8", "#d4f1f2", "#103038"),
    ],
    "Halsa": [
        ("#9c2f4a", "#e07a94", "#fbd9e1", "#5e132b"),
        ("#a8431f", "#e89b5b", "#fbe6cf", "#5e2813"),
        ("#7a2f6b", "#c87ab8", "#f6dcf1", "#3f1538"),
    ],
    "Manniskor": [
        ("#b5651e", "#e0a35b", "#f6e0c8", "#6e3a12"),
        ("#9c5a2c", "#d99c6a", "#f3e2cf", "#5e3416"),
        ("#8a6a2f", "#cda85e", "#f4eccf", "#4f3c16"),
    ],
    "Djur": [
        ("#2f5d3a", "#6aa55f", "#dff0cf", "#163a20"),
        ("#3a5d2f", "#8aa85f", "#e8f0cf", "#1f3a16"),
        ("#2f4d5d", "#5fa0a8", "#d4eef1", "#163840"),
    ],
    "Samhalle": [
        ("#3a3f7a", "#6f74c2", "#d9def0", "#1f2456"),
        ("#3a5a7a", "#5f9bb8", "#d4e8f1", "#163a4f"),
        ("#5a3a7a", "#9b6fc2", "#ecd4f1", "#2f163f"),
    ],
}
DEFAULT_PALETTES = [
    ("#43506b", "#7a8aa0", "#e3e9f0", "#232b3f"),
    ("#5b4350", "#a07a8a", "#f0e3e9", "#2b232b"),
]

# Map real category labels (Swedish, with åäö, and topical aliases) onto the
# ASCII palette/motif keys above so every article gets its category colourway
# instead of falling through to the default.
CATEGORY_ALIASES = {
    "natur": "Natur", "miljö": "Natur", "miljo": "Natur", "klimat": "Natur",
    "teknik": "Teknik", "innovation": "Teknik", "vetenskap": "Teknik",
    "forskning": "Teknik", "rymden": "Teknik", "rymd": "Teknik",
    "hälsa": "Halsa", "halsa": "Halsa", "h\u00e4lsa": "Halsa",
    "människor": "Manniskor", "manniskor": "Manniskor", "folk": "Manniskor",
    "djur": "Djur",
    "samhälle": "Samhalle", "samhalle": "Samhalle", "ekonomi": "Samhalle",
    "kultur": "Samhalle", "utbildning": "Samhalle",
}


def normalize_category(category: str) -> str:
    return CATEGORY_ALIASES.get(category.strip().lower(), "Samhalle")


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


def _category_motif(seed: bytes, category: str, accent: str, thread: str, variant: int) -> str:
    marker = f'data-collage-motif="{category.lower()}"'
    if category == "Natur":
        if variant == 0:
            # A leaf/stem motif built from felt and embroidered vein.
            return (
                f'<g {marker}>'
                f'<path d="M640 660 C520 560 520 380 640 250 C760 380 760 560 640 660 Z" fill="{accent}" opacity="0.82"/>'
                f'<path d="M640 650 V280" stroke="{thread}" stroke-width="6" fill="none" stroke-linecap="round"/>'
                f'<path d="M640 470 C600 450 575 430 552 405 M640 540 C684 520 709 500 732 475" stroke="{thread}" stroke-width="4" fill="none" stroke-linecap="round" opacity="0.8"/>'
                '</g>'
            )
        if variant == 1:
            # A sapling / sprout with two leaves.
            return (
                f'<g {marker}>'
                f'<path d="M640 660 V360" stroke="{thread}" stroke-width="7" fill="none" stroke-linecap="round"/>'
                f'<path d="M640 470 C560 430 520 360 540 320 C610 340 650 410 640 470 Z" fill="{accent}" opacity="0.82"/>'
                f'<path d="M640 420 C720 380 760 310 740 270 C670 290 630 360 640 420 Z" fill="{accent}" opacity="0.7"/>'
                '</g>'
            )
        # variant == 2: rolling hills with a sun.
        return (
            f'<g {marker}>'
            f'<circle cx="800" cy="320" r="58" fill="{accent}" opacity="0.85"/>'
            f'<path d="M120 600 C340 500 460 600 640 540 C820 490 980 580 1160 520 V720 H120 Z" fill="{accent}" opacity="0.8"/>'
            '</g>'
        )
    if category == "Teknik":
        if variant == 0:
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
        if variant == 1:
            # A gear / cog shape.
            return (
                f'<g {marker}>'
                f'<circle cx="640" cy="440" r="120" fill="{accent}" opacity="0.82"/>'
                f'<circle cx="640" cy="440" r="52" fill="{thread}"/>'
                + "".join(
                    f'<rect x="628" y="290" width="24" height="40" rx="6" fill="{accent}" transform="rotate({k * 45} 640 440)"/>'
                    for k in range(8)
                )
                + '</g>'
            )
        # variant == 2: stacked device screens.
        return (
            f'<g {marker}>'
            f'<rect x="470" y="300" width="200" height="140" rx="14" fill="{accent}" opacity="0.82"/>'
            f'<rect x="560" y="420" width="160" height="110" rx="12" fill="{accent}" opacity="0.7"/>'
            f'<rect x="690" y="500" width="130" height="90" rx="10" fill="{accent}" opacity="0.6"/>'
            '</g>'
        )
    if category == "Halsa":
        if variant == 0:
            # A calm heartbeat / pulse stitched line.
            return (
                f'<g {marker}>'
                f'<path d="M400 440 H560 L600 320 L660 560 L700 440 H880" stroke="{thread}" stroke-width="9" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
                f'<circle cx="640" cy="440" r="40" fill="{accent}" opacity="0.8"/>'
                '</g>'
            )
        if variant == 1:
            # A heart made of torn paper.
            return (
                f'<g {marker}>'
                f'<path d="M640 580 C520 480 520 360 600 340 C640 330 640 370 640 380 C640 370 640 330 680 340 C760 360 760 480 640 580 Z" fill="{accent}" opacity="0.84"/>'
                '</g>'
            )
        # variant == 2: a droplet / water motif.
        return (
            f'<g {marker}>'
            f'<path d="M640 300 C720 420 740 500 640 580 C540 500 560 420 640 300 Z" fill="{accent}" opacity="0.82"/>'
            f'<circle cx="640" cy="470" r="30" fill="{thread}" opacity="0.6"/>'
            '</g>'
        )
    if category == "Manniskor":
        if variant == 0:
            # Overlapping friendly figures from torn fabric, no faces.
            return (
                f'<g {marker}>'
                f'<circle cx="560" cy="380" r="46" fill="{accent}"/>'
                f'<path d="M512 600 C512 500 608 500 608 600 Z" fill="{accent}" opacity="0.82"/>'
                f'<circle cx="720" cy="408" r="40" fill="{thread}"/>'
                f'<path d="M680 600 C680 512 760 512 760 600 Z" fill="{thread}" opacity="0.82"/>'
                '</g>'
            )
        if variant == 1:
            # A single figure with open arms.
            return (
                f'<g {marker}>'
                f'<circle cx="640" cy="320" r="44" fill="{accent}"/>'
                f'<path d="M600 600 C600 470 680 470 680 600 Z" fill="{accent}" opacity="0.82"/>'
                f'<path d="M604 470 L470 400 M676 470 L810 400" stroke="{thread}" stroke-width="14" stroke-linecap="round" fill="none"/>'
                '</g>'
            )
        # variant == 2: two linked hands (abstract).
        return (
            f'<g {marker}>'
            f'<path d="M500 420 H640 V480 H500 Z" fill="{accent}" opacity="0.82"/>'
            f'<path d="M780 420 H640 V480 H780 Z" fill="{thread}" opacity="0.82"/>'
            f'<path d="M640 400 V520" stroke="{accent}" stroke-width="10" stroke-linecap="round"/>'
            '</g>'
        )
    if category == "Djur":
        if variant == 0:
            # A soft paw / ear motif in felt.
            return (
                f'<g {marker}>'
                f'<path d="M640 620 C520 560 520 400 640 300 C760 400 760 560 640 620 Z" fill="{accent}" opacity="0.82"/>'
                f'<circle cx="592" cy="360" r="34" fill="{thread}"/>'
                f'<circle cx="688" cy="360" r="34" fill="{thread}"/>'
                f'<path d="M640 392 C612 392 600 416 612 436 H668 C680 416 668 392 640 392 Z" fill="{thread}"/>'
                '</g>'
            )
        if variant == 1:
            # A bird in flight.
            return (
                f'<g {marker}>'
                f'<path d="M460 460 C560 380 600 420 760 420 C640 470 600 470 460 460 Z" fill="{accent}" opacity="0.82"/>'
                f'<path d="M820 400 C720 420 700 460 560 470 C680 430 700 430 820 400 Z" fill="{accent}" opacity="0.7"/>'
                '</g>'
            )
        # variant == 2: a fish / wave motif.
        return (
            f'<g {marker}>'
            f'<path d="M520 440 C600 360 760 360 840 440 C760 520 600 520 520 440 Z" fill="{accent}" opacity="0.82"/>'
            f'<path d="M840 440 L900 400 L900 480 Z" fill="{accent}" opacity="0.82"/>'
            f'<circle cx="580" cy="430" r="10" fill="{thread}"/>'
            '</g>'
        )
    # Samhalle and default: three linked-community variants.
    if variant == 0:
        return (
            f'<g {marker}>'
            f'<circle cx="540" cy="420" r="40" fill="{accent}"/>'
            f'<circle cx="740" cy="400" r="34" fill="{accent}" opacity="0.86"/>'
            f'<circle cx="650" cy="560" r="30" fill="{accent}" opacity="0.8"/>'
            f'<path d="M540 420 L740 400 L650 560 Z" stroke="{thread}" stroke-width="6" fill="none" stroke-linejoin="round"/>'
            '</g>'
        )
    if variant == 1:
        return (
            f'<g {marker}>'
            f'<rect x="500" y="360" width="120" height="120" rx="14" fill="{accent}" opacity="0.82"/>'
            f'<rect x="660" y="360" width="120" height="120" rx="14" fill="{accent}" opacity="0.7"/>'
            f'<rect x="580" y="500" width="120" height="120" rx="14" fill="{accent}" opacity="0.6"/>'
            '</g>'
        )
    return (
        f'<g {marker}>'
        f'<path d="M640 320 L700 480 L560 480 Z" fill="{accent}" opacity="0.82"/>'
        f'<path d="M640 420 L720 600 L560 600 Z" fill="{accent}" opacity="0.7"/>'
        f'<circle cx="640" cy="300" r="26" fill="{thread}"/>'
        '</g>'
    )


def render_svg(item: dict) -> bytes:
    article_id = str(item["id"])
    fingerprint = str(item["source_fingerprint"])
    category = normalize_category(str(item.get("category") or "Samhalle"))
    seed = hashlib.sha256(f"{article_id}:{fingerprint}:{STYLE_VERSION}".encode()).digest()
    # Pick a palette and a motif variant from the article seed so the same
    # category yields several distinct colourways and motifs.
    palettes = CATEGORY_PALETTES.get(category, DEFAULT_PALETTES)
    palette_index = seed[3] % len(palettes)
    palette = palettes[palette_index]
    paper, felt, fabric, thread = palette
    # A warm off-white base that reads as a craft table / backing sheet.
    base = "#f3ece1"
    # Three overlapping torn scraps (paper, felt, fabric) inset from the edges
    # so their ragged borders are visible, each with a soft drop shadow.
    # Positions and rotations shift with the seed so layouts vary.
    angle1 = -2.5 - (seed[5] % 5)
    angle2 = 2.0 + (seed[6] % 5)
    angle3 = -1.5 - (seed[7] % 4)
    scrap1 = _torn_paper(seed, 0, fabric, 60 + seed[8] % 40, 50 + seed[9] % 30, 600 + seed[10] % 80, 440 + seed[11] % 80, angle1, stitch=thread)
    scrap2 = _torn_paper(seed, 1, felt, 540 + seed[12] % 60, 220 + seed[13] % 40, 620 + seed[14] % 80, 480 + seed[15] % 80, angle2, stitch=thread)
    scrap3 = _torn_paper(seed, 2, paper, 340 + seed[16] % 60, 360 + seed[17] % 40, 520 + seed[18] % 80, 360 + seed[19] % 80, angle3, stitch=thread)
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
    motif_variant = seed[4] % 3
    motif = _category_motif(seed, category, felt, thread, motif_variant)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" data-palette="{category.lower()}-{palette_index}" data-motif-variant="{motif_variant}">
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
