#!/usr/bin/env python3
"""Generate category fallback images (health/nature/science/...) via local ComfyUI.

Dependency-free (stdlib). Uses the same Juggernaut-XL workflow as the article
generator. Saves to public/news-images/ai/<category>.webp.
"""
import argparse
import io
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

COMFYUI_URL = "http://127.0.0.1:8000"

CATEGORY_PROMPTS = {
    "health": "peaceful wellness scene, person doing gentle yoga in sunlit Scandinavian home, natural wood interior, plants, calm atmosphere, lifestyle photography, warm natural light, 8k, no text",
    "nature": "serene Nordic nature landscape, misty forest at dawn, soft golden light through pine trees, mossy ground, photorealistic, cinematic, 8k, no text",
    "science": "clean modern research laboratory, soft blue lighting, scientific instruments, futuristic but realistic, scientific photography, 8k, no text",
    "environment": "lush green forest meeting clean river, renewable energy wind turbines in distance, hopeful environmental progress, golden hour, photorealistic, 8k, no text",
    "culture": "bright Scandinavian library and restored historic architecture, warm inviting atmosphere, cultural heritage, architectural photography, 8k, no text",
    "community": "diverse people collaborating in bright modern community workspace, genuine connection, documentary photography, natural light, 8k, no text",
    "progress": "modern sustainable city infrastructure, clean transit, solar panels, hopeful future, architectural photography, golden hour, 8k, no text",
}

NEGATIVE = "text, watermark, signature, logo, title, caption, low quality, blurry, deformed, ugly, bad anatomy, duplicate"

WIDTH, HEIGHT = 1280, 848
REQUEST_TIMEOUT = 180.0
COOLDOWN = 8.0

# Minimal SDXL/Juggernaut workflow (CheckpointLoaderSimple -> CLIPTextEncode x2 -> KSampler -> VAEDecode -> SaveImage)
WORKFLOW = {
    "3": {"inputs": {"seed": 0, "steps": 25, "cfg": 7.0, "sampler_name": "euler_ancestral", "scheduler": "karras", "denoise": 1.0, "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}, "class_type": "KSampler", "_meta": {"title": "KSampler"}},
    "4": {"inputs": {"ckpt_name": "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors"}, "class_type": "CheckpointLoaderSimple", "_meta": {"title": "Load Checkpoint"}},
    "5": {"inputs": {"width": WIDTH, "height": HEIGHT, "batch_size": 1}, "class_type": "EmptyLatentImage", "_meta": {"title": "Empty Latent Image"}},
    "6": {"inputs": {"text": "PROMPT_PLACEHOLDER", "clip": ["4", 1]}, "class_type": "CLIPTextEncode", "_meta": {"title": "Positive"}},
    "7": {"inputs": {"text": NEGATIVE, "clip": ["4", 1]}, "class_type": "CLIPTextEncode", "_meta": {"title": "Negative"}},
    "8": {"inputs": {"samples": ["3", 0], "vae": ["4", 2]}, "class_type": "VAEDecode", "_meta": {"title": "VAE Decode"}},
    "9": {"inputs": {"filename_prefix": "ljusglimt/category", "images": ["8", 0]}, "class_type": "SaveImage", "_meta": {"title": "Save Image"}},
}


def _post(workflow):
    payload = json.dumps({"prompt": workflow, "client_id": "ljusglimt-cat"}).encode()
    req = urllib.request.Request(f"{COMFYUI_URL}/prompt", data=payload, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "LjusglimtCat/1.0"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
        return json.loads(r.read().decode())["prompt_id"]


def _wait(prompt_id, timeout=REQUEST_TIMEOUT):
    url = f"{COMFYUI_URL}/history/{prompt_id}"
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "LjusglimtCat/1.0"}), timeout=10) as r:
                data = json.loads(r.read().decode())
            if prompt_id in data and data[prompt_id].get("outputs"):
                return data[prompt_id]["outputs"]
        except urllib.error.URLError:
            pass
        time.sleep(1.0)
    raise RuntimeError("timeout waiting for ComfyUI")


def _fetch_image(filename, subfolder):
    from urllib.parse import urlencode
    params = urlencode({"filename": filename, "subfolder": subfolder or "", "type": "output"})
    req = urllib.request.Request(f"{COMFYUI_URL}/view?{params}", headers={"User-Agent": "LjusglimtCat/1.0"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
        return r.read()


def _to_webp(png_bytes):
    from PIL import Image
    img = Image.open(io.BytesIO(png_bytes))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    out = io.BytesIO()
    img.save(out, format="WEBP", quality=85, method=6)
    return out.getvalue()


def generate_category(category, out_dir):
    prompt = CATEGORY_PROMPTS[category]
    wf = json.loads(json.dumps(WORKFLOW))
    wf["3"]["inputs"]["seed"] = int(time.time() * 1000) % 2**32
    wf["6"]["inputs"]["text"] = prompt
    pid = _post(wf)
    outputs = _wait(pid)
    for node in outputs.values():
        for img in node.get("images", []):
            raw = _fetch_image(img["filename"], img.get("subfolder", ""))
            webp = _to_webp(raw)
            path = out_dir / f"{category}.webp"
            path.write_bytes(webp)
            return len(webp)
    raise RuntimeError("no image output")


def main():
    base = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", type=Path, default=base / "public/news-images/ai")
    ap.add_argument("--comfyui-url", default=COMFYUI_URL)
    ap.add_argument("--only", nargs="*", default=None)
    args = ap.parse_args()
    if args.comfyui_url:
        globals()["COMFYUI_URL"] = args.comfyui_url

    cats = args.only or list(CATEGORY_PROMPTS.keys())
    ok = 0
    for i, cat in enumerate(cats):
        if cat not in CATEGORY_PROMPTS:
            print(f"skip unknown category: {cat}", file=sys.stderr)
            continue
        try:
            size = generate_category(cat, args.output_dir)
            print(f"{cat}.webp generated ({size} bytes)")
            ok += 1
        except Exception as e:
            print(f"{cat}.webp FAILED: {e}", file=sys.stderr)
        if i < len(cats) - 1:
            time.sleep(COOLDOWN)
    print(f"Category images: {ok}/{len(cats)} generated")
    return 0 if ok == len(cats) else 1


if __name__ == "__main__":
    sys.exit(main())
