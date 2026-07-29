#!/usr/bin/env python3
"""Assign Daniel's preclassified paper collages without CLIP at runtime.

Existing valid one-to-one assignments are preserved. Newly fetched articles
without a verified source image or dedicated AI image receive the highest-rated
unused collage for their editorial category. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

USER_URL_PREFIX = "/news-images/user/"
IMAGE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}$")
DEFAULT_CATEGORY = "Framsteg"


def lacks_primary_image(item: dict) -> bool:
    has_source = item.get("source_image_verified") is True and bool(item.get("source_image_url"))
    return not has_source and not bool(item.get("ai_image"))


def valid_existing(item: dict, known_ids: set[str], used: set[str]) -> str | None:
    image = item.get("user_image")
    if not isinstance(image, dict):
        return None
    image_id = image.get("user_image_id")
    if (not isinstance(image_id, str) or image_id not in known_ids or image_id in used
            or not IMAGE_ID_RE.fullmatch(image_id)
            or image.get("url") != f"{USER_URL_PREFIX}{image_id}.webp"):
        return None
    return image_id


def assign(data: dict, manifest: dict) -> tuple[int, int]:
    entries = manifest.get("images")
    if not isinstance(entries, list) or not entries:
        raise ValueError("category manifest has no images")
    by_id = {entry.get("id"): entry for entry in entries if isinstance(entry, dict)}
    if len(by_id) != len(entries) or any(not isinstance(key, str) or not IMAGE_ID_RE.fullmatch(key) for key in by_id):
        raise ValueError("category manifest contains invalid or duplicate image ids")

    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("news data has no items list")

    targets = [item for item in items if isinstance(item, dict) and lacks_primary_image(item)]
    used: set[str] = set()
    preserved = 0
    pending: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if item not in targets:
            item.pop("user_image", None)
            continue
        image_id = valid_existing(item, set(by_id), used)
        if image_id:
            used.add(image_id)
            preserved += 1
        else:
            item.pop("user_image", None)
            pending.append(item)

    assigned = 0
    for item in pending:
        category = item.get("category") or DEFAULT_CATEGORY
        candidates = []
        for image_id, entry in by_id.items():
            if image_id in used:
                continue
            scores = entry.get("category_scores")
            score = scores.get(category, scores.get(DEFAULT_CATEGORY, -1.0)) if isinstance(scores, dict) else -1.0
            if not isinstance(score, (int, float)) or not math.isfinite(score):
                score = -1.0
            candidates.append((float(score), image_id))
        if not candidates:
            break
        score, image_id = max(candidates, key=lambda pair: (pair[0], pair[1]))
        item["user_image"] = {
            "url": f"{USER_URL_PREFIX}{image_id}.webp",
            "alt": item.get("display_title_sv") or item.get("title") or "Papperscollage från Ljusglimts bildbank",
            "user_image_id": image_id,
            "match_score": round(score, 4),
            "width": 1280,
            "height": 848,
        }
        used.add(image_id)
        assigned += 1
    return preserved, assigned


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--news", default="data/news.json")
    parser.add_argument("--manifest", default="public/news-images/user/category-manifest.json")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    news_path = Path(args.news)
    data = json.loads(news_path.read_text(encoding="utf-8"))
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    preserved, assigned = assign(data, manifest)
    if args.write:
        news_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Paper collages: {preserved} preserved, {assigned} assigned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
