#!/usr/bin/env python3
"""Match Daniel's user images to Ljusglimt articles that lack a source/AI image.

Computes CLIP embeddings for each user image and for each article's text, then
assigns the highest-cosine user image to articles missing both source_image and
ai_image. Writes a `user_image` block into data/news.json. Never touches
source_image_verified or ai_image fields.

Run locally with the ComfyUI venv (has torch + transformers):
  python scripts/match_user_images.py --news data/news.json \
      --user-dir public/news-images/user --write
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from io import BytesIO
from pathlib import Path

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

MODEL_ID = "openai/clip-vit-base-patch32"
TARGET = (1280, 848)
USER_URL_PREFIX = "/news-images/user/"


def cosine(a: list[float], b: list[float]) -> float:
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def load_model():
    model = CLIPModel.from_pretrained(MODEL_ID)
    processor = CLIPProcessor.from_pretrained(MODEL_ID)
    model.eval()
    return model, processor


@torch.no_grad()
def embed_texts(model, processor, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    inputs = processor(text=texts, return_tensors="pt", padding=True, truncation=True)
    out = model.get_text_features(**inputs)
    feats = getattr(out, "text_embeds", None) or out.pooler_output
    feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats.cpu().float().tolist()


@torch.no_grad()
def embed_images(model, processor, images: list[Image.Image]) -> list[list[float]]:
    if not images:
        return []
    inputs = processor(images=images, return_tensors="pt")
    out = model.get_image_features(**inputs)
    feats = getattr(out, "image_embeds", None) or out.pooler_output
    feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats.cpu().float().tolist()


def article_text(item: dict) -> str:
    parts = [
        item.get("display_title_sv") or "",
        item.get("title") or "",
        item.get("agent_summary") or "",
        item.get("source_excerpt") or "",
        item.get("category") or "",
    ]
    return " ".join(p for p in parts if p).strip()


def lacks_image(item: dict) -> bool:
    has_src = item.get("source_image_verified") is True and item.get("source_image_url")
    has_ai = bool(item.get("ai_image"))
    return not has_src and not has_ai


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--news", default="data/news.json")
    ap.add_argument("--user-dir", default="public/news-images/user")
    ap.add_argument("--write", action="store_true", help="Write changes to news.json")
    ap.add_argument("--limit", type=int, default=0, help="Max articles to assign (0=all)")
    ap.add_argument("--max-per-image", type=int, default=1, help="Max times one user image may be reused (default 1 = no repeats)")
    args = ap.parse_args()

    news_path = Path(args.news)
    data = json.loads(news_path.read_text(encoding="utf-8"))
    items = data.get("items", [])

    user_dir = Path(args.user_dir)
    user_files = sorted(user_dir.glob("*.webp"))
    if not user_files:
        print("No user images found", file=sys.stderr)
        return 1

    print(f"Loading CLIP and {len(user_files)} user images...")
    model, processor = load_model()

    user_images = []
    for f in user_files:
        try:
            user_images.append((f, Image.open(f).convert("RGB").resize(TARGET, Image.LANCZOS)))
        except Exception as exc:  # noqa: BLE001
            print(f"skip {f.name}: {exc}")

    user_embs = embed_images(model, processor, [im for _, im in user_images])
    user_names = [f.stem for f, _ in user_images]

    targets = [it for it in items if lacks_image(it)]
    if args.limit:
        targets = targets[: args.limit]
    print(f"Matching {len(targets)} articles without source/ai image...")

    texts = [article_text(it) or it.get("title", "") for it in targets]
    text_embs = embed_texts(model, processor, texts)

    # Greedy capacity-limited assignment: avoid reusing the same user image on
    # multiple articles (which would show one image repeated across the feed).
    # Each image may be used at most max_per_image times; if we run out we
    # relax the cap so every imageless article still gets a fallback.
    n_images = len(user_embs)
    max_per_image = max(1, args.max_per_image)
    usage: dict[int, int] = {i: 0 for i in range(n_images)}
    pairs = []
    for a_idx, emb in enumerate(text_embs):
        for u_idx in range(n_images):
            pairs.append((cosine(emb, user_embs[u_idx]), a_idx, u_idx))
    pairs.sort(reverse=True)

    assigned_to: dict[int, int] = {}
    order = sorted(range(len(targets)), key=lambda a: -max(score for score, b, _ in pairs if b == a))
    for a_idx in order:
        for _, b, u in pairs:
            if b != a_idx:
                continue
            if usage[u] < max_per_image:
                assigned_to[a_idx] = u
                usage[u] += 1
                break

    assigned = 0
    for a_idx, item in enumerate(targets):
        if a_idx not in assigned_to:
            continue
        u = assigned_to[a_idx]
        name = user_names[u]
        score = cosine(text_embs[a_idx], user_embs[u])
        item["user_image"] = {
            "url": f"{USER_URL_PREFIX}{name}.webp",
            "alt": item.get("display_title_sv") or item.get("title") or "Bild från Ljusglimts bildbank",
            "user_image_id": name,
            "match_score": round(score, 4),
            "width": TARGET[0],
            "height": TARGET[1],
        }
        print(f"  {item.get('id')}: {name} (score {score:.3f})")
        assigned += 1

    if args.write:
        news_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {assigned} user_image assignments to {news_path}")
    else:
        print(f"Dry run: {assigned} assignments (use --write to save)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
