#!/usr/bin/env python3
"""
Ljusglimt illustration generator using Z-Image-Turbo (local ComfyUI).
Generates abstract, human-free editorial illustrations for news articles.

CRITICAL: Z-Image-Turbo renders any literal text in the prompt as image text.
Never inject article titles/rubrics (Swedish) into the prompt. Use English
abstract category-based descriptions only.

Run:
  python ljusglimt_zimage_turbo.py --news data/news.json \
      --output-dir public/news-images/ai/articles --max-images 3
"""
import argparse, json, os, time, urllib.request, urllib.error, hashlib
from pathlib import Path
from datetime import datetime, timezone

COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")

# English abstract themes per Swedish category. NO literal text injected.
# IMPORTANT: Z-Image-Turbo at cfg=1.0 follows the prompt literally. The prompt MUST be
# RICH and DETAILED (bold shapes, overlapping forms, rich gradients, strong visual
# rhythm) to get a filled, editorial illustration — NOT a flat/empty background.
# BUT: non-figurative is required — NO literal people, hands, anatomy. Express the
# topic SYMBOLICALLY (nodes, networks, forms, light) so it reads as editorial art,
# not decorative texture, without depicting humans.
CATEGORY_THEMES = {
    "Samhälle": "interconnected glowing network nodes, linked community threads, shared geometric public forms, social cohesion as connected mesh, woven links",
    "Miljö": "lush forests, flowing clean rivers, solar panels catching light, layered earth and leaves, vibrant renewable energy flows",
    "Natur": "underwater seagrass meadows, flowing ocean currents, layered aquatic plants, rippling water light, thriving marine ecosystem forms",
    "Vetenskap": "glowing geometric molecules, light waves rippling through space, orbiting atoms, starfields, intricate discovery patterns",
    "Hälsa": "balanced flowing energy, gentle organic motion, wellness blooms, soft healing light, harmonious restorative forms",
    "Kultur": "swirling paint, music made visible as waves, open books unfolding, creative texture, textured art forms",
    "Teknik": "glowing circuit pathways, flowing data streams, intricate innovation meshes, connected geometry, electric blue networks",
    "Rymden": "starfields, nebula clouds, orbital rings, cosmic geometry, distant planets as cold circles, deep space gradients",
    "Innovation": "glowing circuit pathways, flowing data streams, intricate innovation meshes, connected geometry, electric blue networks, abstract nodes",
    "Ekonomi": "rising intertwined growth curves, exchange as linked golden circles, balanced scales, upward flowing motion",
    "Sport": "dynamic energy bursts, flowing movement curves, powerful motion trails, vibrant athletic rhythm",
    "Utbildning": "open book blooming with light, curious growing shapes, knowledge as radiant geometry, discovery sparks",
    "default": "hope rising as light, growing organic forms, calm yet vibrant curves, harmonious warm gradients",
}

WORKFLOW = {
    "3": {
        "inputs": {
            "seed": 0, "steps": 8, "cfg": 1.0,
            "sampler_name": "res_multistep", "scheduler": "simple", "denoise": 1.0,
            "model": ["11", 0], "positive": ["27", 0], "negative": ["33", 0],
            "latent_image": ["13", 0],
        },
        "class_type": "KSampler", "_meta": {"title": "Kampler"},
    },
    "11": {
        "inputs": {"model": ["28", 0], "beta_schedule": "aura_flow", "sigma_max": 3.0, "shift": 3.0},
        "class_type": "ModelSamplingAuraFlow", "_meta": {"title": "Model Sampling (AuraFlow)"},
    },
    "13": {
        "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
        "class_type": "EmptySD3LatentImage", "_meta": {"title": "Empty SD3 Latent Image"},
    },
    "27": {
        "inputs": {"text": "PROMPT_PLACEHOLDER", "clip": ["30", 0]},
        "class_type": "CLIPTextEncode", "_meta": {"title": "Positive Prompt"},
    },
    "28": {
        "inputs": {"unet_name": "z_image_turbo_bf16.safetensors", "weight_dtype": "default"},
        "class_type": "UNETLoader", "_meta": {"title": "Load Z-Image-Turbo UNET"},
    },
    "29": {
        "inputs": {"vae_name": "ae.safetensors"},
        "class_type": "VAELoader", "_meta": {"title": "Load VAE"},
    },
    "30": {
        "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "lumina2", "device": "default"},
        "class_type": "CLIPLoader", "_meta": {"title": "Load CLIP"},
    },
    "33": {
        "inputs": {"conditioning": ["27", 0]},
        "class_type": "ConditioningZeroOut", "_meta": {"title": "ConditioningZeroOut (negative)"},
    },
    "8": {
        "inputs": {"samples": ["3", 0], "vae": ["29", 0]},
        "class_type": "VAEDecode", "_meta": {"title": "VAE Decode"},
    },
    "9": {
        "inputs": {"images": ["8", 0], "filename_prefix": "ljusglimt_zturbo"},
        "class_type": "SaveImage", "_meta": {"title": "Save Image"},
    },
}

def load_subjects(path: str = "scripts/image_subjects_en.json") -> dict:
    """English subject phrases per article id (pre-translated so Z-Image-Turbo
    never sees Swedish text, which it would render as image text)."""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

SUBJECTS = load_subjects()

def build_prompt_for_article(item: dict) -> str:
    """Realistic, photo-style prompt derived from the individual article's
    subject. English only (Z-Image-Turbo renders literal Swedish text as image
    text). No 'abstract/non-figurative' forcing — we want a real, varied scene
    per article so images are distinct and on-topic.
    """
    aid = item.get("id", "")
    subject = SUBJECTS.get(aid) or item.get("agent_summary") or item.get("title") or ""
    subject = subject.strip()
    if not subject:
        subject = CATEGORY_THEMES.get(item.get("category", ""), CATEGORY_THEMES["default"])
    return (
        f"Realistic photography, ultra detailed, {subject}, "
        "natural lighting, professional editorial photograph, "
        "tack sharp, fully sharp, maximum detail, crisp quality, "
        "high resolution, crystal clear, no blur."
    )

def submit_workflow(prompt: str, seed: int, width=1024, height=1024) -> str:
    wf = json.loads(json.dumps(WORKFLOW))  # deep copy
    wf["27"]["inputs"]["text"] = prompt
    wf["3"]["inputs"]["seed"] = seed
    wf["13"]["inputs"]["width"] = width
    wf["13"]["inputs"]["height"] = height
    payload = json.dumps({"prompt": wf}).encode("utf-8")
    req = urllib.request.Request(
        f"{COMFYUI_URL}/prompt", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())["prompt_id"]

def fetch_result(prompt_id: str, timeout=120) -> bytes:
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(2)
        try:
            with urllib.request.urlopen(f"{COMFYUI_URL}/history/{prompt_id}", timeout=10) as h:
                hist = json.loads(h.read().decode())
            if prompt_id in hist:
                for node_out in hist[prompt_id]["outputs"].values():
                    if "images" in node_out:
                        img = node_out["images"][0]
                        dl = f"{COMFYUI_URL}/view?filename={img['filename']}&subfolder={img.get('subfolder','')}&type=output"
                        with urllib.request.urlopen(dl, timeout=30) as imgr:
                            return imgr.read()
        except urllib.error.HTTPError:
            continue
    raise TimeoutError(f"No result for {prompt_id} in {timeout}s")

def convert_png_to_webp(png_bytes: bytes, quality=88) -> bytes:
    """Convert PNG bytes to WebP using Pillow if available, else passthrough.
    Resizes to 1280x848 to match the site's expected image dimensions."""
    try:
        from io import BytesIO
        from PIL import Image
        img = Image.open(BytesIO(png_bytes)).convert("RGB")
        img = img.resize((1280, 848), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="WEBP", quality=quality)
        return buf.getvalue()
    except Exception:
        return png_bytes  # fallback: keep PNG

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--news", default="data/news.json")
    ap.add_argument("--output-dir", default="public/news-images/ai/articles")
    ap.add_argument("--max-images", type=int, default=3)
    ap.add_argument("--force", action="store_true", help="Regenerate even if ai_image exists")
    ap.add_argument("--regenerate-all", action="store_true",
                    help="Clear all ai_image blocks first, then regenerate every article")
    args = ap.parse_args()

    news_path = Path(args.news)
    data = json.loads(news_path.read_text(encoding="utf-8"))
    items = data.get("items", [])
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.regenerate_all:
        for it in items:
            it.pop("ai_image", None)

    n = 0
    for item in items:
        if n >= args.max_images:
            break
        if "ai_image" in item and not args.force:
            continue
        category = item.get("category", "")
        alt = item.get("title", "") or item.get("agent_summary", "")[:80]
        if not category and not alt:
            continue
        seed = abs(hash(item["id"])) % (2**32)
        print(f"[{n+1}] Genererar för '{alt[:50]}'...")
        pid = submit_workflow(build_prompt_for_article(item), seed)
        png = fetch_result(pid)
        webp = convert_png_to_webp(png)
        # Site expects filename: <article_id>-<source_fingerprint>-v1.webp
        fp = item.get("source_fingerprint", item["id"][:20])
        fname = f"{item['id']}-{fp}-v1.webp"
        fpath = out_dir / fname
        fpath.write_bytes(webp)
        sha = hashlib.sha256(webp).hexdigest()
        item["ai_image"] = {
            "url": f"/news-images/ai/articles/{fname}",
            "alt": alt,
            "model": "comfyui-z-image-turbo",
            "prompt_version": "z-image-turbo-v1",
            "source_fingerprint": fp,
            "width": 1280, "height": 848,
            "sha256": sha,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        n += 1

    news_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Klar. {n} bilder genererade och news.json uppdaterad.")

if __name__ == "__main__":
    main()
