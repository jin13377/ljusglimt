#!/usr/bin/env python3
"""Fail closed unless a news update adds valid, local generated-image metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from datetime import datetime
from pathlib import Path


MAX_CHANGED_ARTICLES = 3
EXPECTED_WIDTH = 1280
EXPECTED_HEIGHT = 848
EXPECTED_MODEL = "gpt-image-2"
EXPECTED_PROMPT_VERSION = "editorial-concept-v1"
MAX_IMAGE_BYTES = 2 * 1024 * 1024
HEX_20_RE = re.compile(r"[0-9a-f]{20}\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
GENERATED_AT_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z\Z")
AI_IMAGE_KEYS = {
    "url",
    "alt",
    "model",
    "prompt_version",
    "source_fingerprint",
    "width",
    "height",
    "sha256",
    "generated_at",
}


def _riff_chunks(payload: bytes) -> list[tuple[bytes, bytes]]:
    if len(payload) < 12 or payload[:4] != b"RIFF" or payload[8:12] != b"WEBP":
        raise ValueError("generated image is not a WebP RIFF file")
    declared_size = int.from_bytes(payload[4:8], "little")
    if declared_size != len(payload) - 8:
        raise ValueError("generated WebP has an invalid RIFF length")

    chunks: list[tuple[bytes, bytes]] = []
    offset = 12
    while offset < len(payload):
        if offset + 8 > len(payload):
            raise ValueError("generated WebP has a truncated chunk header")
        fourcc = payload[offset:offset + 4]
        size = int.from_bytes(payload[offset + 4:offset + 8], "little")
        start = offset + 8
        end = start + size
        padded_end = end + (size & 1)
        if end > len(payload) or padded_end > len(payload):
            raise ValueError("generated WebP has a truncated chunk")
        if size & 1 and payload[end:padded_end] != b"\x00":
            raise ValueError("generated WebP has invalid chunk padding")
        chunks.append((fourcc, payload[start:end]))
        offset = padded_end
    if offset != len(payload):
        raise ValueError("generated WebP has trailing bytes")
    return chunks


def _vp8_dimensions(chunk: bytes) -> tuple[int, int]:
    if len(chunk) < 10 or chunk[3:6] != b"\x9d\x01\x2a" or chunk[0] & 1:
        raise ValueError("generated WebP has an invalid VP8 key frame")
    width = int.from_bytes(chunk[6:8], "little") & 0x3FFF
    height = int.from_bytes(chunk[8:10], "little") & 0x3FFF
    return width, height


def _vp8l_dimensions(chunk: bytes) -> tuple[int, int]:
    if len(chunk) < 5 or chunk[0] != 0x2F:
        raise ValueError("generated WebP has an invalid VP8L header")
    bits = int.from_bytes(chunk[1:5], "little")
    if bits >> 29:
        raise ValueError("generated WebP uses an unsupported VP8L version")
    return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1


def _vp8x_dimensions(chunk: bytes) -> tuple[int, int]:
    if len(chunk) != 10:
        raise ValueError("generated WebP has an invalid VP8X header")
    if chunk[0] & 0x02:
        raise ValueError("animated WebP files are not allowed")
    width = int.from_bytes(chunk[4:7], "little") + 1
    height = int.from_bytes(chunk[7:10], "little") + 1
    return width, height


def validate_webp(payload: bytes, width: int = EXPECTED_WIDTH, height: int = EXPECTED_HEIGHT) -> None:
    """Validate the WebP container, still-image bitstream header and dimensions."""
    if not payload or len(payload) > MAX_IMAGE_BYTES:
        raise ValueError("generated WebP has an invalid file size")
    chunks = _riff_chunks(payload)
    if any(fourcc in {b"ANIM", b"ANMF"} for fourcc, _ in chunks):
        raise ValueError("animated WebP files are not allowed")

    extended = [chunk for fourcc, chunk in chunks if fourcc == b"VP8X"]
    if len(extended) > 1:
        raise ValueError("generated WebP contains duplicate VP8X headers")
    if extended and _vp8x_dimensions(extended[0]) != (width, height):
        raise ValueError(f"generated WebP must be {width}x{height}")

    image_chunks = [(fourcc, chunk) for fourcc, chunk in chunks if fourcc in {b"VP8 ", b"VP8L"}]
    if len(image_chunks) != 1:
        raise ValueError("generated WebP must contain exactly one still-image bitstream")
    fourcc, image_chunk = image_chunks[0]
    dimensions = _vp8_dimensions(image_chunk) if fourcc == b"VP8 " else _vp8l_dimensions(image_chunk)
    if dimensions != (width, height):
        raise ValueError(f"generated WebP must be {width}x{height}")


def _without_ai_image(item: dict) -> dict:
    return {key: value for key, value in item.items() if key != "ai_image"}


def _validate_generated_at(value: object, article_id: str) -> None:
    if not isinstance(value, str) or not GENERATED_AT_RE.fullmatch(value):
        raise ValueError(f"ai_image.generated_at for {article_id} must be an RFC 3339 UTC timestamp")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"ai_image.generated_at for {article_id} is invalid") from exc


def _safe_regular_image(images_dir: Path, filename: str) -> Path:
    images_dir = Path(images_dir)
    if images_dir.parts[-4:] != ("public", "news-images", "ai", "articles"):
        raise ValueError("images directory must be public/news-images/ai/articles")
    root = images_dir.parents[3]
    relative_parts = ("public", "news-images", "ai", "articles", filename)
    cursor = root
    for index, part in enumerate(relative_parts):
        cursor = cursor / part
        try:
            info = os.lstat(cursor)
        except FileNotFoundError as exc:
            raise ValueError(f"generated image file is missing: {filename}") from exc
        if stat.S_ISLNK(info.st_mode):
            raise ValueError(f"generated image path may not contain symlinks: {filename}")
        if index < len(relative_parts) - 1 and not stat.S_ISDIR(info.st_mode):
            raise ValueError(f"generated image parent is not a directory: {filename}")
        if index == len(relative_parts) - 1 and not stat.S_ISREG(info.st_mode):
            raise ValueError(f"generated image is not a regular file: {filename}")

    articles_root = images_dir.resolve(strict=True)
    resolved = cursor.resolve(strict=True)
    if resolved.parent != articles_root:
        raise ValueError(f"generated image escapes the article image directory: {filename}")
    return resolved


def _validate_ai_image(item: dict, images_dir: Path) -> None:
    article_id = item.get("id")
    fingerprint = item.get("source_fingerprint")
    image = item.get("ai_image")
    if item.get("public_eligible") is not True:
        raise ValueError(f"generated image article {article_id} must be public_eligible")
    if not isinstance(article_id, str) or not HEX_20_RE.fullmatch(article_id):
        raise ValueError("changed article id must be exactly 20 lowercase hexadecimal characters")
    if not isinstance(fingerprint, str) or not HEX_20_RE.fullmatch(fingerprint):
        raise ValueError(f"source_fingerprint for {article_id} must be exactly 20 lowercase hexadecimal characters")
    if not isinstance(image, dict) or set(image) != AI_IMAGE_KEYS:
        raise ValueError(f"ai_image for {article_id} must contain exactly the approved fields")

    expected_filename = f"{article_id}-{fingerprint[:8]}-v1.webp"
    expected_url = f"/news-images/ai/articles/{expected_filename}"
    if image["url"] != expected_url:
        raise ValueError(f"ai_image.url for {article_id} must be {expected_url}")
    if image["source_fingerprint"] != fingerprint:
        raise ValueError(f"ai_image.source_fingerprint for {article_id} does not match the source")
    if image["model"] != EXPECTED_MODEL:
        raise ValueError(f"ai_image.model for {article_id} must be {EXPECTED_MODEL}")
    if image["prompt_version"] != EXPECTED_PROMPT_VERSION:
        raise ValueError(
            f"ai_image.prompt_version for {article_id} must be {EXPECTED_PROMPT_VERSION}"
        )
    if type(image["width"]) is not int or type(image["height"]) is not int:
        raise ValueError(f"ai_image dimensions for {article_id} must be integers")
    if (image["width"], image["height"]) != (EXPECTED_WIDTH, EXPECTED_HEIGHT):
        raise ValueError(f"ai_image dimensions for {article_id} must be {EXPECTED_WIDTH}x{EXPECTED_HEIGHT}")
    if not isinstance(image["sha256"], str) or not SHA256_RE.fullmatch(image["sha256"]):
        raise ValueError(f"ai_image.sha256 for {article_id} must be lowercase hexadecimal")
    alt = image["alt"]
    if (not isinstance(alt, str) or not alt or alt != alt.strip() or len(alt) > 400
            or any(ord(character) < 32 for character in alt)):
        raise ValueError(f"ai_image.alt for {article_id} is invalid")
    _validate_generated_at(image["generated_at"], article_id)

    path = _safe_regular_image(images_dir, expected_filename)
    payload = path.read_bytes()
    validate_webp(payload)
    actual_sha256 = hashlib.sha256(payload).hexdigest()
    if image["sha256"] != actual_sha256:
        raise ValueError(f"ai_image.sha256 for {article_id} does not match the file")


def validate_generated_image_changes(
    before: dict,
    after: dict,
    images_dir: Path,
    max_changes: int = MAX_CHANGED_ARTICLES,
) -> None:
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ValueError("news documents must be JSON objects")

    before_meta = {key: value for key, value in before.items() if key != "items"}
    after_meta = {key: value for key, value in after.items() if key != "items"}
    if before_meta != after_meta:
        raise ValueError("top-level news metadata changed")

    before_items = before.get("items")
    after_items = after.get("items")
    if not isinstance(before_items, list) or not isinstance(after_items, list):
        raise ValueError("items must be arrays")
    if len(before_items) != len(after_items):
        raise ValueError("articles were added or removed")

    changed: list[dict] = []
    for index, (old, new) in enumerate(zip(before_items, after_items, strict=True)):
        if not isinstance(old, dict) or not isinstance(new, dict):
            raise ValueError(f"item {index} must be an object")
        article_id = old.get("id") or f"index {index}"
        if _without_ai_image(old) != _without_ai_image(new):
            raise ValueError(f"non-image fields changed for {article_id}")
        if old.get("ai_image") != new.get("ai_image"):
            changed.append(new)

    if type(max_changes) is not int or not 0 <= max_changes <= MAX_CHANGED_ARTICLES:
        raise ValueError(f"max_changes must be between 0 and {MAX_CHANGED_ARTICLES}")
    if len(changed) > max_changes:
        raise ValueError(f"at most {max_changes} articles may receive generated images per run")
    for item in changed:
        _validate_ai_image(item, Path(images_dir))


def main() -> int:
    base = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument(
        "--images-dir",
        type=Path,
        default=base / "public/news-images/ai/articles",
    )
    parser.add_argument("--max-changes", type=int, default=MAX_CHANGED_ARTICLES)
    args = parser.parse_args()
    before = json.loads(args.before.read_text(encoding="utf-8"))
    after = json.loads(args.after.read_text(encoding="utf-8"))
    validate_generated_image_changes(before, after, args.images_dir, args.max_changes)
    print("Validated: generated image metadata and local WebP files only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
