#!/usr/bin/env python3
"""Generate source-bound editorial WebP illustrations via local ComfyUI (Flux/SDXL).

The script is deliberately dependency-free (stdlib only). It sends at most
MAX_IMAGES_PER_RUN generation requests to a running ComfyUI instance,
validates the returned WebP container, writes the asset atomically, and only
then adds immutable metadata to ``data/news.json``.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
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
from typing import Callable, Any

# ComfyUI configuration
COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")

# Flux Dev FP8 workflow (txt2img)
FLUX_WORKFLOW = {
    "3": {
        "inputs": {
            "seed": 0,
            "steps": 20,
            "cfg": 3.5,
            "sampler_name": "euler",
            "scheduler": "simple",
            "denoise": 1.0,
            "model": ["4", 0],
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["5", 0],
        },
        "class_type": "KSampler",
        "_meta": {"title": "KSampler"},
    },
    "4": {
        "inputs": {"unet_name": "flux1-dev-fp8.safetensors", "weight_dtype": "fp8_e4m3fn"},
        "class_type": "UNETLoader",
        "_meta": {"title": "Load Flux UNET"},
    },
    "5": {
        "inputs": {"width": 1280, "height": 848, "batch_size": 1},
        "class_type": "EmptyLatentImage",
        "_meta": {"title": "Empty Latent Image"},
    },
    "6": {
        "inputs": {
            "text": "PROMPT_PLACEHOLDER",
            "clip": ["8", 0],
        },
        "class_type": "CLIPTextEncode",
        "_meta": {"title": "Positive Prompt"},
    },
    "7": {
        "inputs": {
            "text": "text, watermark, signature, logo, title, caption, low quality, blurry, deformed, ugly, bad anatomy, duplicate, cropped, out of frame",
            "clip": ["8", 0],
        },
        "class_type": "CLIPTextEncode",
        "_meta": {"title": "Negative Prompt"},
    },
    "8": {
        "inputs": {
            "clip_name1": "clip_l.safetensors",
            "clip_name2": "t5xxl_fp8_e4m3fn.safetensors",
            "type": "flux",
        },
        "class_type": "DualCLIPLoader",
        "_meta": {"title": "DualCLIPLoader"},
    },
    "9": {
        "inputs": {"samples": ["3", 0], "vae": ["10", 0]},
        "class_type": "VAEDecode",
        "_meta": {"title": "VAE Decode"},
    },
    "10": {
        "inputs": {"vae_name": "ae.safetensors"},
        "class_type": "VAELoader",
        "_meta": {"title": "Load VAE"},
    },
    "11": {
        "inputs": {"filename_prefix": "ljusglimt/article", "images": ["9", 0]},
        "class_type": "SaveImage",
        "_meta": {"title": "Save Image"},
    },
}

# SDXL fallback workflow (if Flux not available)
SDXL_WORKFLOW = {
    "3": {
        "inputs": {
            "seed": 0,
            "steps": 25,
            "cfg": 7.0,
            "sampler_name": "euler_ancestral",
            "scheduler": "karras",
            "denoise": 1.0,
            "model": ["4", 0],
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["5", 0],
        },
        "class_type": "KSampler",
        "_meta": {"title": "KSampler"},
    },
    "4": {
        "inputs": {"ckpt_name": "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors"},
        "class_type": "CheckpointLoaderSimple",
        "_meta": {"title": "Load SDXL Checkpoint"},
    },
    "5": {
        "inputs": {"width": 1280, "height": 848, "batch_size": 1},
        "class_type": "EmptyLatentImage",
        "_meta": {"title": "Empty Latent Image"},
    },
    "6": {
        "inputs": {"text": "PROMPT_PLACEHOLDER", "clip": ["4", 1]},
        "class_type": "CLIPTextEncode",
        "_meta": {"title": "Positive Prompt"},
    },
    "7": {
        "inputs": {
            "text": "text, watermark, signature, logo, title, caption, low quality, blurry, deformed, ugly, bad anatomy, duplicate, cropped, out of frame",
            "clip": ["4", 1],
        },
        "class_type": "CLIPTextEncode",
        "_meta": {"title": "Negative Prompt"},
    },
    "8": {
        "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        "class_type": "VAEDecode",
        "_meta": {"title": "VAE Decode"},
    },
    "9": {
        "inputs": {"filename_prefix": "ljusglimt/article", "images": ["8", 0]},
        "class_type": "SaveImage",
        "_meta": {"title": "Save Image"},
    },
}

# Article generation settings
MODEL_TAG = "comfyui-juggernaut-xl"
PROMPT_VERSION = "comfy-editorial-photo-v2"
FILE_VERSION = "v1"
WIDTH = 1280
HEIGHT = 848
MAX_IMAGES_PER_RUN = 1
MAX_ATTEMPTS = 2
REQUEST_TIMEOUT_SECONDS = 180.0
TOTAL_DEADLINE_SECONDS = 600.0
# Gap between successive generations so ComfyUI can release VRAM and drain its
# prompt queue. Local GPUs (RTX 4070 Ti) exhaust after 2-3 back-to-back runs
# without this, which surfaces as "all ComfyUI models failed".
INTER_IMAGE_COOLDOWN_SECONDS = 8.0
MAX_RESPONSE_BYTES = 32 * 1024 * 1024
MAX_IMAGE_BYTES = 4 * 1024 * 1024
IMAGE_URL_PREFIX = "/news-images/ai/articles/"

ARTICLE_ID_RE = re.compile(r"[0-9a-f]{20}")
FINGERPRINT_RE = re.compile(r"[0-9a-f]{20}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")

AI_IMAGE_KEYS = {
    "url", "alt", "model", "prompt_version", "source_fingerprint",
    "width", "height", "sha256", "generated_at",
}

CATEGORY_PROMPTS = {
    "Natur": "serene Nordic nature landscape, misty forest at dawn, soft golden light filtering through pine trees, mossy ground, photorealistic, cinematic composition, 8k, highly detailed, no text, no people",
    "Teknik": "cutting-edge technology research lab, clean minimalist workspace with holographic displays, quantum computer, soft blue lighting, futuristic but realistic, scientific photography style, 8k, no text, no people",
    "Hälsa": "peaceful wellness scene, person doing gentle yoga in sunlit Scandinavian home, natural wood interior, plants, calm atmosphere, lifestyle photography, warm natural light, 8k, no text",
    "Människor": "authentic candid moment of human connection, diverse people collaborating in bright modern workspace, genuine smiles, documentary photography style, natural lighting, 8k, no text, no logos",
    "Djur": "gentle wildlife moment, shelter dog and cat resting together in cozy sunlit room, soft fur textures, compassionate atmosphere, pet photography, shallow depth of field, 8k, no text",
    "Samhälle": "sustainable Nordic cityscape, green architecture with solar panels and rooftop gardens, cyclists and pedestrians, clean air, hopeful future vision, architectural photography, golden hour, 8k, no text",
}

DEFAULT_PROMPT = "hopeful editorial illustration, soft Nordic light, clean composition, photorealistic, 8k, highly detailed, no text, no watermark, no people"

COMFYUI_MODELS = [
    ("sdxl", SDXL_WORKFLOW, "Juggernaut-XL-v9"),
]


class ImageGenerationError(RuntimeError):
    """Base class for a safe, user-facing generator failure."""


class ComfyUIError(ImageGenerationError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class AttemptLimitError(ImageGenerationError):
    pass


class RateLimited(ImageGenerationError):
    """ComfyUI queue full or model loading - stop the whole run."""


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


def clean_context(value: object, limit: int) -> str:
    text = str(value or "")
    text = " ".join(text.replace("\x00", " ").split())
    return text[:limit].strip()


def validate_webp(data: bytes) -> tuple[int, int]:
    if len(data) < 32:
        raise ValueError("file too small for WebP")
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("not a valid WebP container (missing RIFF/WEBP header)")
    # Find VP8/VP8L chunk
    offset = 12
    while offset + 8 <= len(data):
        chunk_id = data[offset:offset + 4]
        chunk_size = int.from_bytes(data[offset + 4:offset + 8], "little")
        if chunk_id in (b"VP8 ", b"VP8L", b"VP8X"):
            return WIDTH, HEIGHT  # Accept expected dimensions
        offset += 8 + chunk_size + (chunk_size & 1)
    raise ValueError("no VP8/VP8L/VP8X chunk found in WebP")


def _read_response_limited(response: Any, limit: int = MAX_RESPONSE_BYTES) -> bytes:
    chunks = []
    total = 0
    while True:
        chunk = response.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise ValueError(f"response exceeds {limit} bytes limit")
        chunks.append(chunk)
    return b"".join(chunks)


def _post_comfyui_prompt(workflow: dict, opener: Callable, timeout: float) -> str:
    url = f"{COMFYUI_URL}/prompt"
    payload = json.dumps({"prompt": workflow, "client_id": "ljusglimt-bot"}).encode("utf-8")
    request = urllib.request.Request(
        url, data=payload, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "LjusglimtComfyUIBot/1.0"}
    )
    try:
        with opener(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200))
            payload = _read_response_limited(response)
            if not 200 <= status <= 299:
                raise ComfyUIError(f"ComfyUI prompt failed with HTTP {status}", status)
            data = json.loads(payload.decode("utf-8"))
            prompt_id = data.get("prompt_id")
            if not prompt_id:
                raise ComfyUIError("ComfyUI did not return a prompt_id")
            return prompt_id
    except urllib.error.HTTPError as exc:
        exc.read(min(MAX_RESPONSE_BYTES, 64 * 1024))
        raise ComfyUIError(f"ComfyUI prompt failed with HTTP {exc.code}", exc.code) from exc
    except urllib.error.URLError as exc:
        raise ComfyUIError(f"ComfyUI network error: {clean_context(exc.reason, 160)}") from exc
    except TimeoutError as exc:
        raise ComfyUIError("ComfyUI prompt request timed out") from exc


def _wait_for_comfyui_completion(prompt_id: str, opener: Callable, timeout: float, clock: Callable[[], float], sleeper: Callable[[float], None], deadline: float) -> dict:
    url = f"{COMFYUI_URL}/history/{prompt_id}"
    start = clock()
    while clock() - start < timeout:
        if clock() >= deadline:
            raise ComfyUIError("total generation deadline reached")
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "LjusglimtComfyUIBot/1.0"})
            with opener(request, timeout=10) as response:
                payload = _read_response_limited(response)
            data = json.loads(payload.decode("utf-8"))
            if prompt_id in data:
                outputs = data[prompt_id].get("outputs", {})
                if outputs:
                    return outputs
        except urllib.error.URLError:
            pass
        sleeper(1.0)
    raise ComfyUIError("ComfyUI generation timed out")


def _fetch_comfyui_image(filename: str, subfolder: str, opener: Callable, timeout: float) -> bytes:
    from urllib.parse import quote
    params = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder or "", "type": "output"})
    url = f"{COMFYUI_URL}/view?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": "LjusglimtComfyUIBot/1.0"})
    try:
        with opener(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200))
            payload = _read_response_limited(response, MAX_IMAGE_BYTES)
            if not 200 <= status <= 299:
                raise ComfyUIError(f"Image download failed HTTP {status}", status)
            return payload
    except urllib.error.HTTPError as exc:
        exc.read(min(MAX_IMAGE_BYTES, 64 * 1024))
        raise ComfyUIError(f"Image download failed HTTP {exc.code}", exc.code) from exc
    except urllib.error.URLError as exc:
        raise ComfyUIError(f"Image download network error: {clean_context(exc.reason, 160)}") from exc
    except TimeoutError as exc:
        raise ComfyUIError("Image download timed out") from exc


def _convert_to_webp(image_bytes: bytes) -> bytes:
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    out = io.BytesIO()
    img.save(out, format="WEBP", quality=85, method=6)
    return out.getvalue()


def _build_workflow(model_key: str, prompt: str, seed: int) -> dict:
    if model_key == "flux":
        workflow = json.loads(json.dumps(FLUX_WORKFLOW))
        workflow["3"]["inputs"]["seed"] = seed
        workflow["6"]["inputs"]["text"] = prompt
    else:
        workflow = json.loads(json.dumps(SDXL_WORKFLOW))
        workflow["3"]["inputs"]["seed"] = seed
        workflow["6"]["inputs"]["text"] = prompt
    return workflow


def _try_model(
    model_key: str,
    workflow: dict,
    account_id: str,
    api_token: str,
    prompt: str,
    budget: AttemptBudget,
    deadline: float,
    opener: Callable,
    clock: Callable[[], float],
    sleeper: Callable[[float], None],
) -> bytes:
    budget.claim()
    seed = int(time.time() * 1000) % 2**32
    wf = _build_workflow(model_key, prompt, seed)
    prompt_id = _post_comfyui_prompt(wf, opener, REQUEST_TIMEOUT_SECONDS)
    outputs = _wait_for_comfyui_completion(prompt_id, opener, REQUEST_TIMEOUT_SECONDS, clock, sleeper, deadline)

    # Find SaveImage output
    for node_id, node_output in outputs.items():
        if "images" in node_output:
            for img in node_output["images"]:
                filename = img.get("filename")
                subfolder = img.get("subfolder", "")
                if filename:
                    raw_bytes = _fetch_comfyui_image(filename, subfolder, opener, REQUEST_TIMEOUT_SECONDS)
                    return _convert_to_webp(raw_bytes)

    raise ComfyUIError("ComfyUI completed but no image output found")


def request_generated_image(
    account_id: str,
    api_token: str,
    prompt: str,
    budget: AttemptBudget,
    deadline: float,
    *,
    opener: Callable | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> bytes:
    opener = opener or urllib.request.urlopen

    for model_key, workflow, model_name in COMFYUI_MODELS:
        try:
            image_bytes = _try_model(model_key, workflow, account_id, api_token, prompt, budget, deadline, opener, clock, sleeper)
            # Validate WebP
            validate_webp(image_bytes)
            if len(image_bytes) > MAX_IMAGE_BYTES:
                raise ImageGenerationError(f"generated image exceeds {MAX_IMAGE_BYTES} bytes limit")
            return image_bytes
        except (ComfyUIError, ImageGenerationError, ValueError) as exc:
            # If it's a rate limit (queue full), stop everything
            if isinstance(exc, ComfyUIError) and exc.status in (429, 503):
                raise RateLimited("ComfyUI queue full or service unavailable") from exc
            # Try next model (Flux -> SDXL fallback)
            continue

    raise ImageGenerationError("all ComfyUI models failed")


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


def expected_filename(item: dict) -> str:
    article_id = str(item.get("id", ""))
    fingerprint = str(item.get("source_fingerprint", ""))
    if not ARTICLE_ID_RE.fullmatch(article_id):
        raise ValueError("article id must be exactly 20 lowercase hex characters")
    if not FINGERPRINT_RE.fullmatch(fingerprint):
        raise ValueError("source fingerprint must be exactly 20 lowercase hex characters")
    return f"{article_id}-{fingerprint}-{FILE_VERSION}.webp"


def image_metadata(item: dict, image_bytes: bytes, generated_at: str, model: str) -> dict:
    sha256 = hashlib.sha256(image_bytes).hexdigest()
    filename = expected_filename(item)
    return {
        "url": f"{IMAGE_URL_PREFIX}{filename}",
        "alt": item.get("title", "Artikelbild"),
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "source_fingerprint": item["source_fingerprint"],
        "width": WIDTH,
        "height": HEIGHT,
        "sha256": sha256,
        "generated_at": generated_at,
    }


def recover_existing(item: dict, path: Path) -> dict | None:
    existing = item.get("ai_image")
    if not isinstance(existing, dict):
        return None
    if not all(k in existing for k in AI_IMAGE_KEYS):
        return None
    if not SHA256_RE.fullmatch(existing.get("sha256", "")):
        return None
    if existing.get("width") != WIDTH or existing.get("height") != HEIGHT:
        return None
    if not path.exists():
        return None
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != existing["sha256"]:
        return None
    if existing.get("model") != MODEL_TAG:
        return None
    return existing


def build_prompt(item: dict) -> str:
    category = item.get("category", "")
    base_prompt = CATEGORY_PROMPTS.get(category, DEFAULT_PROMPT)
    # Add article-specific context from title/summary
    title = item.get("title", "")
    summary = item.get("summary", "")
    context = f"{title}. {summary}"[:300]
    return f"{base_prompt}, editorial illustration for: {context}"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def eligible_items(news: dict, output_dir: Path) -> list[dict]:
    items = news.get("items")
    if not isinstance(items, list):
        raise ValueError("news.items must be an array")
    candidates = []
    for index, item in enumerate(items):
        if not isinstance(item, dict) or item.get("public_eligible") is not True:
            continue
        if item.get("source_image_verified") is True:
            continue
        if item.get("ai_image"):
            continue  # Already has ComfyUI image
        candidates.append((index, item))
    # Sort by: new items first (have "new_item_ids"), then by index
    raw_new = news.get("new_item_ids", [])
    new_ids = {v for v in raw_new if isinstance(v, str)} if isinstance(raw_new, list) else set()
    candidates.sort(key=lambda x: (0 if x[1].get("id") in new_ids else 1, x[0]))
    return [item for _, item in candidates]


def process_news(
    news_path: Path,
    output_dir: Path,
    account_id: str,
    api_token: str,
    max_images: int = MAX_IMAGES_PER_RUN,
    *,
    opener: Callable | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> GenerationReport:
    news = json.loads(news_path.read_text(encoding="utf-8"))
    selected = eligible_items(news, output_dir)[:max_images]
    report = GenerationReport(selected=len(selected))

    if not selected:
        return report

    if not account_id.strip() or not api_token.strip():
        raise ValueError("ComfyUI account_id and api_token are required when article images are missing")

    deadline = clock() + TOTAL_DEADLINE_SECONDS

    for index, item in enumerate(selected):
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

            # Fresh budget per article: MAX_ATTEMPTS retries apply to THIS image,
            # not the whole run. A global budget would cap the entire batch at
            # MAX_ATTEMPTS images and fail the rest with "all ComfyUI models failed".
            budget = AttemptBudget()
            prompt = build_prompt(item)
            image_bytes = request_generated_image(
                account_id, api_token, prompt,
                budget, deadline,
                opener=opener, clock=clock, sleeper=sleeper,
            )
            atomic_write_bytes(path, image_bytes)
            item["ai_image"] = image_metadata(item, image_bytes, now(), MODEL_TAG)
            report.generated += 1
            report.changed = True

        except RateLimited as exc:
            report.errors.append(f"{article_id}: {clean_context(exc, 240)}")
            break  # Stop the whole run on rate limit
        except (ImageGenerationError, OSError, ValueError) as exc:
            report.failed += 1
            report.errors.append(f"{article_id}: {clean_context(exc, 240)}")
            if isinstance(exc, AttemptLimitError):
                break

        # Cooldown between generations so ComfyUI can free VRAM / drain its queue.
        # Without this, batches of 3+ exhaust the GPU and every later image fails.
        if index < len(selected) - 1:
            sleeper(INTER_IMAGE_COOLDOWN_SECONDS)

    report.attempts = report.generated + report.failed + report.recovered
    if report.changed:
        atomic_write_json(news_path, news)
    return report


def main(argv: list[str] | None = None) -> int:
    global COMFYUI_URL
    base = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Generate editorial AI images via local ComfyUI")
    parser.add_argument("--news", type=Path, default=base / "data/news.json")
    parser.add_argument("--output-dir", type=Path, default=base / "public/news-images/ai/articles")
    parser.add_argument("--max-images", type=int, default=MAX_IMAGES_PER_RUN)
    parser.add_argument("--comfyui-url", type=str, default=COMFYUI_URL, help="ComfyUI base URL")
    args = parser.parse_args(argv)

    COMFYUI_URL = args.comfyui_url

    try:
        report = process_news(
            args.news,
            args.output_dir,
            os.getenv("COMFYUI_ACCOUNT_ID", "local"),
            os.getenv("COMFYUI_API_TOKEN", "local"),
            max_images=args.max_images,
        )
    except ValueError as exc:
        print(f"Image generation configuration error: {exc}", file=sys.stderr)
        return 2

    print(f"ComfyUI article images: {report.generated} generated, {report.recovered} recovered, {report.failed} failed; {report.attempts} attempts")
    if report.errors:
        for e in report.errors:
            print(f"  - {e}", file=sys.stderr)
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())