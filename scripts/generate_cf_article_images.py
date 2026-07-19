#!/usr/bin/env python3
"""Generate editorial WebP illustrations via Cloudflare Workers AI (free tier).

A drop-in, dependency-light alternative to ``generate_article_images.py`` that
uses the site's existing Cloudflare account instead of a paid OpenAI key. It
sends at most three image requests per run, resizes the model output to the
canonical 1280x848 WebP, writes the asset atomically and only then records
immutable ``ai_image`` metadata in ``data/news.json``. If credentials are
missing or a request fails, the article keeps its free local SVG fallback.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

# Cloudflare Workers AI text-to-image models, tried in order. Lucid Origin
# (Leonardo.AI) gives the most professional editorial photos on the free tier.
# Leonardo Phoenix is a warm paper-collage style kept as automatic fallback if
# Lucid Origin is rate-limited or fails. FLUX schnell was noticeably rougher.
MODELS = [
    {
        "id": "@cf/leonardo/lucid-origin",
        "tag": "cf-lucid-origin",
        "prompt_version": "cf-editorial-photo-v1",
        "style": "photo",
    },
    {
        "id": "@cf/leonardo/phoenix-1.0",
        "tag": "cf-leonardo-phoenix",
        "prompt_version": "cf-editorial-collage-v1",
        "style": "collage",
    },
]
MODEL = MODELS[0]["id"]
MODEL_TAG = MODELS[0]["tag"]
PROMPT_VERSION = MODELS[0]["prompt_version"]
FILE_VERSION = "v1"
WIDTH = 1280
HEIGHT = 848
STEPS = 6
# One image per scheduled run. The Cloudflare Workers AI free tier has a
# tight per-account rate quota on text-to-image; generating at most one
# image per night spreads requests across many nights instead of
# burning the quota on a single run. We also make only ONE
# API attempt per run: on the first 429 we stop immediately
# (leaving every article on its local SVG fallback) and let tomorrow's
# scheduled run retry. This keeps the quota free for the next night
# instead of burning all attempts on a rate-limited account.
MAX_IMAGES_PER_RUN = 1
MAX_ATTEMPTS = 1
REQUEST_TIMEOUT_SECONDS = 120.0
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
    """Base class for a safe, user-facing generator failure."""


class ApiError(ImageGenerationError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status
        # 429 = the provider's free-tier quota is exhausted. We treat
        # this as fatal for the whole run (see RateLimited) so we do not
        # burn the rest of the quota or starve other articles.
        self.rate_limited = status == 429

    @property
    def retryable(self) -> bool:
        # 429 is NOT retried: stop immediately and let later runs retry.
        return self.status is not None and 500 <= self.status <= 599


class AttemptLimitError(ImageGenerationError):
    pass


class RateLimited(ImageGenerationError):
    """The provider's free-tier rate quota is exhausted for now.

    Treated as fatal for the whole run: we stop generating, leave every
    article on its local SVG fallback, and let tomorrow's scheduled run
    retry (spreading image creation across many nights instead of
    burning the entire per-account quota on a single run).
    """


@dataclass
class AttemptBudget:
    used: int = 0

    def claim(self) -> None:
        if self.used >= MAX_ATTEMPTS:
            raise AttemptLimitError("the global API attempt limit was reached")
        self.used += 1


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


def valid_iso_z(value: object) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.tzinfo is not None


def clean_context(value: object, limit: int) -> str:
    text = str(value or "")
    text = " ".join(text.replace("\x00", " ").split())
    return text[:limit].strip()


def build_alt(item: dict) -> str:
    title = clean_context(item.get("title"), 300)
    return f"Konceptuell AI-illustration till nyheten: {title}"[:400]


# Category -> concrete symbolic subject hint, so images vary by topic.
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
    """Build a topic-hinted prompt WITHOUT injecting untrusted title verbatim.

    The article title/excerpt are untrusted; we only derive a safe category
    subject hint from the trusted category field and never paste the raw title
    into the prompt as an instruction.
    """
    category = clean_context(item.get("category"), 40).lower()
    subject = CATEGORY_SUBJECT.get(category, "a warm symbolic editorial scene")
    if style == "collage":
        return (
            "Wide landscape editorial illustration in a handmade Scandinavian "
            "paper-collage and gouache style, torn coloured paper, felt, soft "
            "layered shapes and gentle light. "
            f"Subject: {subject}, shown symbolically — not a specific event. "
            "Symbolic and hopeful, illustrative rather than documentary. "
            "No text, no letters, no numbers, no captions, no logos, no brands, "
            "no watermarks, no people, no faces, no identifiable individuals."
        )
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


def _u24le(value: bytes) -> int:
    return value[0] | value[1] << 8 | value[2] << 16


def validate_webp(data: bytes, width: int = WIDTH, height: int = HEIGHT) -> tuple[int, int]:
    """Validate a non-animated RIFF/WebP and return its canvas dimensions."""
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageGenerationError("generated image exceeds the 2 MB limit")
    if len(data) < 20 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ImageGenerationError("generated image is not a RIFF/WebP file")
    riff_size = int.from_bytes(data[4:8], "little")
    if riff_size + 8 != len(data):
        raise ImageGenerationError("WebP RIFF length is inconsistent")

    offset = 12
    canvas: tuple[int, int] | None = None
    frame: tuple[int, int] | None = None
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
            canvas = (_u24le(payload[4:7]) + 1, _u24le(payload[7:10]) + 1)
        elif kind == b"VP8 ":
            image_chunks += 1
            if len(payload) < 10 or payload[3:6] != b"\x9d\x01\x2a":
                raise ImageGenerationError("invalid VP8 frame header")
            frame = (
                int.from_bytes(payload[6:8], "little") & 0x3FFF,
                int.from_bytes(payload[8:10], "little") & 0x3FFF,
            )
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
    """Resize/crop any raw model image to a 1280x848 opaque WebP under 2 MB."""
    from PIL import Image  # local import so tests can skip if Pillow is absent

    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception as exc:  # noqa: BLE001 - Pillow raises many types
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
        or not valid_iso_z(metadata.get("generated_at"))
    ):
        return False
    try:
        data = read_file_limited(output_dir / filename)
    except (OSError, ImageGenerationError):
        return False
    return hashlib.sha256(data).hexdigest() == metadata["sha256"]


def eligible_items(news: dict, output_dir: Path) -> list[dict]:
    items = news.get("items")
    if not isinstance(items, list):
        raise ValueError("news.items must be an array")
    raw_new = news.get("new_item_ids", [])
    new_ids = {v for v in raw_new if isinstance(v, str)} if isinstance(raw_new, list) else set()
    candidates: list[tuple[int, int, dict]] = []
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


def _read_response_limited(response) -> bytes:
    payload = response.read(MAX_RESPONSE_BYTES + 1)
    if len(payload) > MAX_RESPONSE_BYTES:
        raise ApiError("Workers AI response exceeds the size limit")
    return payload


def _decode_cf_image(payload: bytes) -> bytes:
    """Workers AI returns JSON {result:{image:<base64>}} or a raw image body."""
    if payload[:4] == b"RIFF" or payload[:8] == b"\x89PNG\r\n\x1a\n":
        return payload
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApiError("Workers AI returned an unreadable response") from exc
    if isinstance(decoded, dict) and decoded.get("success") is False:
        errors = decoded.get("errors") or []
        message = clean_context(errors[0].get("message") if errors and isinstance(errors[0], dict) else "", 160)
        raise ApiError(f"Workers AI error: {message or 'unknown'}")
    result = decoded.get("result") if isinstance(decoded, dict) else None
    encoded = result.get("image") if isinstance(result, dict) else None
    if not isinstance(encoded, str):
        raise ApiError("Workers AI response does not contain image data")
    try:
        return base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ApiError("Workers AI returned invalid base64 image data") from exc


def _post_image_request(
    account_id: str,
    api_token: str,
    prompt: str,
    model_id: str,
    timeout: float,
    opener: Callable | None = None,
) -> bytes:
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model_id}"
    body = json.dumps({"prompt": prompt, "steps": STEPS}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "LjusglimtCfImageBot/1.0",
    })
    open_url = opener or urllib.request.urlopen
    try:
        with open_url(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200))
            payload = _read_response_limited(response)
            if not 200 <= status <= 299:
                if status == 429:
                    # Free-tier quota exhausted: fatal for the whole run.
                    raise RateLimited("Workers AI rate limit (HTTP 429) reached")
                raise ApiError(f"Workers AI returned HTTP {status}", status)
    except urllib.error.HTTPError as exc:
        exc.read(min(MAX_RESPONSE_BYTES, 64 * 1024))
        if exc.code == 429:
            raise RateLimited("Workers AI rate limit (HTTP 429) reached") from exc
        raise ApiError(f"Workers AI returned HTTP {exc.code}", exc.code) from exc
    except urllib.error.URLError as exc:
        raise ApiError(f"Workers AI network error: {clean_context(exc.reason, 160)}") from exc
    except TimeoutError as exc:
        raise ApiError("Workers AI request timed out") from exc

    raw = _decode_cf_image(payload)
    return to_canonical_webp(raw)


def request_generated_image(
    account_id: str,
    api_token: str,
    prompt: str,
    budget: AttemptBudget,
    deadline: float,
    *,
    model_entry: dict,
    opener: Callable | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> bytes:
    for local_attempt in range(2):
        remaining = deadline - clock()
        if remaining <= 0:
            raise ImageGenerationError("the total generation deadline was reached")
        budget.claim()
        try:
            return _post_image_request(
                account_id, api_token, prompt, model_entry["id"],
                min(REQUEST_TIMEOUT_SECONDS, remaining), opener,
            )
        except ApiError as exc:
            if not exc.retryable or local_attempt == 1:
                raise
            remaining = deadline - clock()
            if remaining <= 0:
                raise ImageGenerationError("the total generation deadline was reached") from exc
            sleeper(min(1.0, remaining))
    raise AssertionError("unreachable")


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


def recover_existing(item: dict, path: Path) -> dict | None:
    try:
        data = read_file_limited(path)
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except (OSError, ImageGenerationError):
        return None
    return image_metadata(item, data, modified)


def process_news(
    news_path: Path,
    output_dir: Path,
    account_id: str,
    api_token: str,
    *,
    max_images: int = MAX_IMAGES_PER_RUN,
    opener: Callable | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] = utc_now,
) -> GenerationReport:
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
    if not account_id.strip() or not api_token.strip():
        raise ValueError("CF_ACCOUNT_ID and CF_IMAGE_API_TOKEN are required when article images are missing")

    budget = AttemptBudget()
    deadline = clock() + TOTAL_DEADLINE_SECONDS
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
            image = None
            last_error: Exception | None = None
            for model_entry in MODELS:
                try:
                    image = request_generated_image(
                        account_id, api_token,
                        build_prompt(item, model_entry["style"]),
                        budget, deadline, model_entry=model_entry,
                        opener=opener, clock=clock, sleeper=sleeper,
                    )
                    break
                except RateLimited:
                    # Hard rate limit: stop the entire run immediately.
                    # Do not try fallback models — they share the same quota.
                    raise
                except (ImageGenerationError, OSError, ValueError) as exc:
                    last_error = exc
                    # try next model in the chain (e.g. Lucid Origin -> Phoenix)
                    continue
            if image is None:
                # All models failed (e.g. network/non-429). Try next article,
                # but if the failure was a hard rate limit, stop the whole run.
                if isinstance(last_error, RateLimited):
                    raise last_error
                raise last_error or ImageGenerationError("all models failed")
            atomic_write_bytes(path, image)
            item["ai_image"] = image_metadata(item, image, now(), model_entry)
            report.generated += 1
            report.changed = True
        except (ImageGenerationError, OSError, ValueError) as exc:
            if isinstance(exc, RateLimited):
                # Free-tier quota exhausted: stop now, leave every article on
                # its local SVG fallback, let tomorrow's run retry.
                report.errors.append(f"{article_id}: {clean_context(exc, 240)}")
                break
            report.failed += 1
            report.errors.append(f"{article_id}: {clean_context(exc, 240)}")
            if isinstance(exc, AttemptLimitError):
                break

    report.attempts = budget.used
    if report.changed:
        atomic_write_json(news_path, news)
    return report


def main(argv: list[str] | None = None) -> int:
    base = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Generate editorial AI images via Cloudflare Workers AI")
    parser.add_argument("--news", type=Path, default=base / "data/news.json")
    parser.add_argument("--output-dir", type=Path, default=base / "public/news-images/ai/articles")
    parser.add_argument("--max-images", type=int, default=MAX_IMAGES_PER_RUN)
    args = parser.parse_args(argv)
    try:
        report = process_news(
            args.news,
            args.output_dir,
            os.getenv("CF_ACCOUNT_ID", ""),
            os.getenv("CF_IMAGE_API_TOKEN", ""),
            max_images=args.max_images,
        )
    except ValueError as exc:
        print(f"Image generation configuration error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Image generation filesystem error: {exc}", file=sys.stderr)
        return 1

    for error in report.errors:
        print(f"Image generation failed for {error}", file=sys.stderr)
    print(
        f"CF article images: {report.generated} generated, {report.recovered} recovered, "
        f"{report.failed} failed; {report.attempts} API attempts."
    )
    return 1 if report.selected and not (report.generated or report.recovered) else 0


if __name__ == "__main__":
    raise SystemExit(main())
