#!/usr/bin/env python3
"""Generate editorial WebP illustrations via LOCAL ComfyUI (no cloud quota).

A drop-in sibling of ``generate_cf_article_images.py`` that uses a locally
running ComfyUI server (http://127.0.0.1:8188) instead of Cloudflare Workers AI.
This means:
  * NO per-account rate quota -- your RTX 4070 Ti SUPER has unlimited local runs.
  * Generated images are written as static 1280x848 WebP into the same
    ``public/news-images/ai/articles/`` path and recorded with the same
    ``ai_image`` metadata contract as the CF generator, so the front-end
    ``resolveAiImage`` only needs to accept the new ``model`` tag to light up.

This file does NOT edit ``src/lib/news.ts`` or the CI validator -- that is a
separate, intentional step left for later. It is safe to run as a local test
(``--test-prompt``) without touching the deployed site.

NOTE: a *local* ComfyUI server only exists on this machine. The scheduled GitHub
Actions run has no GPU and cannot reach 127.0.0.1:8188. To use ComfyUI in CI you
would need a reachable ComfyUI endpoint (a small GPU host / a self-hosted
runner). Until then, run this generator locally and commit the resulting static
WebP + news.json, exactly like the free-SVG path already works.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Local ComfyUI server (your machine). Override with --server.
COMFY_SERVER = os.getenv("COMFY_SERVER", "http://127.0.0.1:8188")

# Which model(s) to use. Primär = SDXL (already installed). Add Flux fp8 here
# later by dropping in a flux_txt2img.json and its node map.
MODELS = [
    {
        "id": "comfyui-sdxl",
        "tag": "comfyui-sdxl",
        "prompt_version": "comfy-editorial-photo-v1",
        "style": "photo",
        "workflow": Path(__file__).resolve().parent.parent
        / "scripts/comfy_workflows/sdxl_txt2img.json",
        # Node ids from sdxl_txt2img.json:
        "prompt_node": "6",
        "negative_node": "7",
        "seed_node": "3",
        "steps_node": "3",
        "size_node": "5",
    },
    {
        "id": "comfyui-flux",
        "tag": "comfyui-flux",
        "prompt_version": "comfy-editorial-photo-v2",
        "style": "photo",
        "workflow": Path(__file__).resolve().parent.parent
        / "scripts/comfy_workflows/flux_txt2img.json",
        # Node ids from flux_txt2img.json (same layout as sdxl):
        "prompt_node": "6",
        "negative_node": "7",
        "seed_node": "3",
        "steps_node": "3",
        "size_node": "5",
    },
]
MODEL = MODELS[0]["id"]
MODEL_TAG = MODELS[0]["tag"]
PROMPT_VERSION = MODELS[0]["prompt_version"]
FILE_VERSION = "v1"
WIDTH = 1280
HEIGHT = 848
STEPS = 28
MAX_IMAGES_PER_RUN = 3  # mirrors the CI validator's MAX_CHANGED_ARTICLES
REQUEST_TIMEOUT_SECONDS = 300.0
TOTAL_DEADLINE_SECONDS = 480.0
MAX_RESPONSE_BYTES = 24 * 1024 * 1024
MAX_IMAGE_BYTES = 2 * 1024 * 1024
IMAGE_URL_PREFIX = "/news-images/ai/articles/"

ARTICLE_ID_RE = re.compile(r"[0-9a-f]{20}")
FINGERPRINT_RE = re.compile(r"[0-9a-f]{20}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
AI_IMAGE_KEYS = {
    "url", "alt", "model", "prompt_version", "source_fingerprint",
    "width", "height", "sha256", "generated_at",
}


class ImageGenerationError(RuntimeError):
    pass


@dataclass
class GenerationReport:
    selected: int = 0
    generated: int = 0
    recovered: int = 0
    failed: int = 0
    attempts: int = 0
    changed: bool = False
    errors: list[str] = field(default_factory=list)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def clean_context(value: object, limit: int) -> str:
    text = str(value or "")
    text = " ".join(text.replace("\x00", " ").split())
    return text[:limit].strip()


def build_alt(item: dict) -> str:
    title = clean_context(item.get("title"), 300)
    return f"Konceptuell AI-illustration till nyheten: {title}"[:400]


# Category -> concrete symbolic subject hint, so images vary by topic.
# (Mirrors generate_cf_article_images.CATEGORY_SUBJECT so the style stays consistent.)
CATEGORY_SUBJECT = {
    "natur": "leaves, sprouts, forest and rolling hills in warm green tones",
    "miljö": "clean nature, water and greenery, hopeful ecology",
    "klimat": "clean nature, water and greenery, hopeful ecology",
    "teknik": "abstract circuits, gentle machinery and soft blue light",
    "innovation": "abstract ideas, light bulbs of shape and colour, soft blue light",
    "vetenskap": "abstract discovery, molecules, telescopes and soft light",
    "rymden": "stars, planets and a calm cosmic sky",
    "hälsa": "calm wellbeing, a heart shape, water and soft rose tones",
    "människor": "abstract friendly figures without faces, open and warm",
    "djur": "a gentle friendly animal in nature, symbolic and warm",
    "samhälle": "connected community shapes, buildings and bridges",
    "ekonomi": "growth shapes, coins abstracted, upward gentle lines",
    "kultur": "art, music and colour, warm and inviting",
    "utbildning": "books, learning shapes and warm light",
}


def build_prompt(item: dict, style: str = "photo") -> str:
    """Topic-hinted prompt WITHOUT untrusted title verbatim (content-safety)."""
    category = clean_context(item.get("category"), 40).lower()
    subject = CATEGORY_SUBJECT.get(category, "a warm symbolic editorial scene")
    return (
        "Wide landscape editorial photograph, natural soft daylight, shallow "
        "depth of field, warm Scandinavian tone, professional stock-photo quality. "
        f"Subject: {subject}, shown symbolically — not a specific event. "
        "Hopeful, calm and credible. "
        "No text, no letters, no numbers, no captions, no logos, no brands, "
        "no watermarks, no people, no faces, no identifiable individuals."
    )


def item_identity(item: dict) -> tuple[str, str]:
    article_id = str(item.get("id") or "")
    fingerprint = str(item.get("source_fingerprint") or "")
    if ARTICLE_ID_RE.fullmatch(article_id) is None:
        raise ValueError("article id must be exactly 20 lowercase hexadecimal characters")
    if FINGERPRINT_RE.fullmatch(fingerprint) is None:
        raise ValueError("source_fingerprint must be exactly 20 lowercase hexadecimal characters")
    return article_id, fingerprint


def expected_filename(item: dict) -> str:
    article_id, fingerprint = item_identity(item)
    return f"{article_id}-{fingerprint[:8]}-{FILE_VERSION}.webp"


def expected_url(item: dict) -> str:
    return IMAGE_URL_PREFIX + expected_filename(item)


# ---- image validation (identical contract to the CF generator) ----

def validate_webp(data: bytes, width: int = WIDTH, height: int = HEIGHT) -> tuple[int, int]:
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageGenerationError("generated image exceeds the 2 MB limit")
    if len(data) < 20 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ImageGenerationError("generated image is not a RIFF/WebP file")
    riff_size = int.from_bytes(data[4:8], "little")
    if riff_size + 8 != len(data):
        raise ImageGenerationError("WebP RIFF length is inconsistent")

    offset = 12
    canvas = None
    frame = None
    image_chunks = 0
    while offset < len(data):
        if offset + 8 > len(data):
            raise ImageGenerationError("WebP contains a truncated chunk header")
        kind = data[offset:offset + 4]
        size = int.from_bytes(data[offset + 4:offset + 8], "little")
        start = offset + 8
        end = start + size
        padded_end = end + (size & 1)
        if end > len(data) or padded_end > len(data):
            raise ImageGenerationError("WebP contains a truncated chunk")
        payload = data[start:end]
        if kind in {b"ANIM", b"ANMF"}:
            raise ImageGenerationError("animated WebP images are not allowed")
        if kind == b"VP8X":
            if len(payload) < 10:
                raise ImageGenerationError("invalid VP8X header")
            if payload[0] & 0x02:
                raise ImageGenerationError("animated WebP images are not allowed")
            canvas = (payload[1] | payload[2] << 8 | payload[3] << 16,
                      payload[4] | payload[5] << 8 | payload[6] << 16)
        elif kind == b"VP8 ":
            image_chunks += 1
            if len(payload) < 10 or payload[3:6] != b"\x9d\x01\x2a":
                raise ImageGenerationError("invalid VP8 frame header")
            frame = (int.from_bytes(payload[6:8], "little") & 0x3FFF,
                     int.from_bytes(payload[8:10], "little") & 0x3FFF)
        elif kind == b"VP8L":
            image_chunks += 1
            if len(payload) < 5 or payload[0] != 0x2F:
                raise ImageGenerationError("invalid VP8L frame header")
            packed = int.from_bytes(payload[1:5], "little")
            frame = ((packed & 0x3FFF) + 1, ((packed >> 14) & 0x3FFF) + 1)
        offset = padded_end
    if offset != len(data) or image_chunks != 1 or frame is None:
        raise ImageGenerationError("WebP must contain exactly one still image frame")
    if canvas is not None and canvas != frame:
        raise ImageGenerationError("WebP canvas and frame dimensions differ")
    dimensions = canvas or frame
    if dimensions != (width, height):
        raise ImageGenerationError(
            f"generated image has dimensions {dimensions[0]}x{dimensions[1]}, expected {width}x{height}"
        )
    return dimensions


def read_file_limited(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise ImageGenerationError("image asset is missing or is not a regular file")
    if path.stat().st_size > MAX_IMAGE_BYTES:
        raise ImageGenerationError("image asset exceeds the 2 MB limit")
    data = path.read_bytes()
    validate_webp(data)
    return data


def to_canonical_webp(raw: bytes) -> bytes:
    """Resize/crop any raw model image (PNG) to a 1280x848 opaque WebP under 2 MB."""
    from PIL import Image  # local import so the script can be inspected without Pillow

    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception as exc:
        raise ImageGenerationError("model returned an unreadable image") from exc
    image = image.convert("RGB")
    src_w, src_h = image.size
    if src_w < 8 or src_h < 8:
        raise ImageGenerationError("model image is too small")
    scale = max(WIDTH / src_w, HEIGHT / src_h)
    new_w, new_h = round(src_w * scale), round(src_h * scale)
    image = image.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - WIDTH) // 2
    top = (new_h - HEIGHT) // 2
    image = image.crop((left, top, left + WIDTH, top + HEIGHT))
    for quality in (82, 72, 62, 50):
        buffer = io.BytesIO()
        image.save(buffer, "WEBP", quality=quality, method=6)
        data = buffer.getvalue()
        if len(data) <= MAX_IMAGE_BYTES:
            validate_webp(data)
            return data
    raise ImageGenerationError("could not compress image under the 2 MB limit")


def image_metadata(item: dict, data: bytes, generated_at: datetime, model_entry: dict) -> dict:
    _, fingerprint = item_identity(item)
    return {
        "url": expected_url(item),
        "alt": build_alt(item),
        "model": model_entry["tag"],
        "prompt_version": model_entry["prompt_version"],
        "source_fingerprint": fingerprint,
        "width": WIDTH,
        "height": HEIGHT,
        "sha256": hashlib.sha256(data).hexdigest(),
        "generated_at": iso_z(generated_at),
    }


# ---- local ComfyUI client ----

def _comfy_post(server: str, path: str, body: bytes | None, timeout: float) -> dict:
    req = urllib.request.Request(
        f"{server}{path}",
        data=body,
        method="POST" if body is not None else "GET",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.URLError as exc:
        raise ImageGenerationError(f"ComfyUI unreachable at {server}: {clean_context(exc.reason, 160)}") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImageGenerationError("ComfyUI returned an unreadable response") from exc


def _comfy_get(server: str, path: str, timeout: float) -> bytes:
    req = urllib.request.Request(f"{server}{path}", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.URLError as exc:
        raise ImageGenerationError(f"ComfyUI unreachable at {server}: {clean_context(exc.reason, 160)}") from exc


def submit_to_comfyui(model_entry: dict, prompt: str, seed: int,
                      timeout: float, server: str = COMFY_SERVER) -> bytes:
    """Inject prompt/seed/size into the model's workflow and wait for the PNG."""
    workflow_path = model_entry["workflow"]
    if not Path(workflow_path).is_file():
        raise ImageGenerationError(f"workflow not found: {workflow_path}")
    workflow = json.loads(Path(workflow_path).read_text(encoding="utf-8"))
    wf = workflow[model_entry["prompt_node"]]["inputs"]
    wf["text"] = prompt
    if model_entry.get("negative_node"):
        workflow[model_entry["negative_node"]]["inputs"]["text"] = (
            "ugly, blurry, low quality, deformed, watermark, text, oversaturated, extra limbs"
        )
    if model_entry.get("seed_node"):
        workflow[model_entry["seed_node"]]["inputs"]["seed"] = seed
    if model_entry.get("steps_node"):
        workflow[model_entry["steps_node"]]["inputs"]["steps"] = STEPS
    if model_entry.get("size_node"):
        workflow[model_entry["size_node"]]["inputs"]["width"] = WIDTH
        workflow[model_entry["size_node"]]["inputs"]["height"] = HEIGHT

    result = _comfy_post(server, "/prompt", json.dumps({"prompt": workflow}).encode(), timeout)
    prompt_id = result.get("prompt_id")
    if not prompt_id:
        raise ImageGenerationError(f"ComfyUI /prompt did not return a prompt_id: {result}")

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        history = _comfy_get(server, f"/history/{prompt_id}", timeout)
        hist = json.loads(history.decode("utf-8"))
        if prompt_id in hist:
            outputs = hist[prompt_id].get("outputs", {})
            for node_id, out in outputs.items():
                imgs = out.get("images")
                if imgs:
                    img = imgs[0]
                    params = urllib.parse.urlencode({
                        "filename": img["filename"],
                        "subfolder": img.get("subfolder", ""),
                        "type": img.get("type", ""),
                    })
                    return _comfy_get(server, f"/view?{params}", timeout)
        time.sleep(2.0)
    raise ImageGenerationError("ComfyUI generation timed out (history never completed)")


# ---- standalone test (does NOT touch news.json / deploy) ----

def test_generate(prompt: str, output_path: Path, server: str = COMFY_SERVER, model: dict = MODELS[0]) -> Path:
    """Generate one image from a free-text prompt and save it for preview."""
    import random
    output_path.parent.mkdir(parents=True, exist_ok=True)
    seed = random.randint(0, 2**63)
    raw = submit_to_comfyui(model, prompt, seed, REQUEST_TIMEOUT_SECONDS, server)
    # Save both a PNG preview and the canonical WebP.
    png_path = output_path.with_suffix(".png")
    png_path.write_bytes(raw)
    webp = to_canonical_webp(raw)
    output_path.write_bytes(webp)
    return output_path


# ---- full process_news (mirror of CF; ready, but run only when you connect it) ----

def is_current_ai_image(item: dict, output_dir: Path) -> bool:
    metadata = item.get("ai_image")
    if not isinstance(metadata, dict) or set(metadata) != AI_IMAGE_KEYS:
        return False
    try:
        _, fingerprint = item_identity(item)
        filename = expected_filename(item)
    except ValueError:
        return False
    if (
        metadata.get("url") != IMAGE_URL_PREFIX + filename
        or metadata.get("alt") != build_alt(item)
        or metadata.get("model") not in {m["tag"] for m in MODELS}
        or metadata.get("prompt_version") not in {m["prompt_version"] for m in MODELS}
        or metadata.get("source_fingerprint") != fingerprint
        or metadata.get("width") != WIDTH
        or metadata.get("height") != HEIGHT
        or SHA256_RE.fullmatch(str(metadata.get("sha256") or "")) is None
        or not _valid_iso_z(metadata.get("generated_at"))
    ):
        return False
    try:
        data = read_file_limited(output_dir / filename)
    except (OSError, ImageGenerationError):
        return False
    return hashlib.sha256(data).hexdigest() == metadata["sha256"]


def _valid_iso_z(value: object) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return True


def eligible_items(news: dict, output_dir: Path) -> list[dict]:
    items = news.get("items")
    if not isinstance(items, list):
        raise ValueError("news.items must be an array")
    raw_new = news.get("new_item_ids", [])
    new_ids = {v for v in raw_new if isinstance(v, str)} if isinstance(raw_new, list) else set()
    candidates = []
    for index, item in enumerate(items):
        if not isinstance(item, dict) or item.get("public_eligible") is not True:
            continue
        if item.get("source_image_verified") is True:
            continue
        try:
            article_id, _ = item_identity(item)
        except ValueError:
            continue
        if not is_current_ai_image(item, output_dir):
            candidates.append((0 if article_id in new_ids else 1, index, item))
    candidates.sort(key=lambda value: (value[0], value[1]))
    return [item for _, _, item in candidates]


def recover_existing(item: dict, path: Path) -> dict | None:
    try:
        data = read_file_limited(path)
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except (OSError, ImageGenerationError):
        return None
    return image_metadata(item, data, modified, MODELS[0])


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def atomic_write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def process_news(news_path: Path, output_dir: Path, *,
                 max_images: int = MAX_IMAGES_PER_RUN,
                 server: str = COMFY_SERVER,
                 model: dict = MODELS[0],
                 now: object = utc_now) -> GenerationReport:
    if not 1 <= max_images <= MAX_IMAGES_PER_RUN:
        raise ValueError(f"max_images must be between 1 and {MAX_IMAGES_PER_RUN}")
    try:
        news = json.loads(news_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read valid news JSON: {exc}") from exc
    if not isinstance(news, dict):
        raise ValueError("news document must be an object")

    selected = eligible_items(news, output_dir)[:max_images]
    report = GenerationReport(selected=len(selected))
    if not selected:
        return report

    deadline = time.monotonic() + TOTAL_DEADLINE_SECONDS
    for item in selected:
        article_id = str(item.get("id") or "unknown")
        try:
            filename = expected_filename(item)
            path = output_dir / filename
            recovered = recover_existing(item, path)
            if recovered is not None:
                item["ai_image"] = recovered
                report.recovered += 1
                report.changed = True
                continue
            import random
            seed = random.randint(0, 2**63)
            raw = submit_to_comfyui(model, build_prompt(item), seed,
                                    min(REQUEST_TIMEOUT_SECONDS, deadline - time.monotonic()), server)
            webp = to_canonical_webp(raw)
            atomic_write_bytes(path, webp)
            item["ai_image"] = image_metadata(item, webp, now(), model)
            report.generated += 1
            report.changed = True
        except (ImageGenerationError, OSError, ValueError) as exc:
            report.failed += 1
            report.errors.append(f"{article_id}: {clean_context(exc, 240)}")

    if report.changed:
        atomic_write_json(news_path, news)
    return report


def main(argv: list[str] | None = None) -> int:
    base = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Generate editorial AI images via local ComfyUI")
    parser.add_argument("--news", type=Path, default=base / "data/news.json")
    parser.add_argument("--output-dir", type=Path, default=base / "public/news-images/ai/articles")
    parser.add_argument("--max-images", type=int, default=MAX_IMAGES_PER_RUN)
    parser.add_argument("--server", default=COMFY_SERVER)
    parser.add_argument("--model", choices=[m["id"] for m in MODELS], default=MODELS[0]["id"],
                        help="Which ComfyUI model entry to use (sdxl or flux).")
    parser.add_argument("--test-prompt", metavar="TEXT",
                        help="Generate ONE preview image from TEXT and exit. Does not touch news.json.")
    parser.add_argument("--test-out", type=Path, default=base / "public/news-images/ai/articles/_preview.webp")
    args = parser.parse_args(argv)

    if args.test_prompt:
        model = next(m for m in MODELS if m["id"] == args.model)
        out = test_generate(args.test_prompt, args.test_out, args.server, model)
        print(f"Preview image written: {out}")
        print(f"Also saved PNG: {out.with_suffix('.png')}")
        return 0

    try:
        model = next(m for m in MODELS if m["id"] == args.model)
        report = process_news(args.news, args.output_dir, max_images=args.max_images,
                             server=args.server, model=model)
    except ValueError as exc:
        print(f"Image generation configuration error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Image generation filesystem error: {exc}", file=sys.stderr)
        return 1

    for error in report.errors:
        print(f"Image generation failed for {error}", file=sys.stderr)
    print(
        f"ComfyUI article images: {report.generated} generated, {report.recovered} recovered, "
        f"{report.failed} failed."
    )
    return 1 if report.selected and not (report.generated or report.recovered) else 0


if __name__ == "__main__":
    raise SystemExit(main())
