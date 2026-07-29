#!/usr/bin/env python3
"""Build offline category scores for Daniel's paper-collage library.

Run locally with the ComfyUI venv after importing new images. The scheduled
workflow consumes the resulting JSON and does not load CLIP or call any API.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from match_user_images import TARGET, cosine, embed_images, embed_texts, load_model

CATEGORY_PROMPTS = {
    "Djur": "a hopeful editorial paper collage about animals, pets, wildlife, rescue and friendship",
    "Hälsa": "a hopeful editorial paper collage about health, medicine, care, wellbeing and recovery",
    "Miljö": "a hopeful editorial paper collage about clean energy, climate solutions and sustainability",
    "Natur": "a hopeful editorial paper collage about forests, oceans, plants, conservation and biodiversity",
    "Vetenskap": "a hopeful editorial paper collage about science, research, space, discovery and technology",
    "Kultur": "a hopeful editorial paper collage about art, music, books, creativity and cultural heritage",
    "Människor": "a hopeful editorial paper collage about people, community, education, volunteers and cooperation",
    "Framsteg": "a hopeful editorial paper collage about progress, innovation, solutions and a brighter future",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-dir", default="public/news-images/user")
    parser.add_argument("--output", default="public/news-images/user/category-manifest.json")
    args = parser.parse_args()

    files = sorted(Path(args.user_dir).glob("*.webp"))
    if not files:
        raise SystemExit("No user WebP images found")
    model, processor = load_model()
    categories = list(CATEGORY_PROMPTS)
    text_embeddings = embed_texts(model, processor, [CATEGORY_PROMPTS[key] for key in categories])
    image_embeddings = []
    batch_size = 8
    for start in range(0, len(files), batch_size):
        batch = []
        for path in files[start:start + batch_size]:
            with Image.open(path) as opened:
                batch.append(opened.convert("RGB").resize(TARGET, Image.Resampling.LANCZOS))
        image_embeddings.extend(embed_images(model, processor, batch))
        print(f"Classified {min(start + batch_size, len(files))}/{len(files)} images")

    payload = {
        "version": 1,
        "model": "openai/clip-vit-base-patch32",
        "images": [
            {
                "id": path.stem,
                "category_scores": {
                    category: round(cosine(image_embedding, text_embeddings[index]), 6)
                    for index, category in enumerate(categories)
                },
            }
            for path, image_embedding in zip(files, image_embeddings)
        ],
    }
    output = Path(args.output)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote category scores for {len(files)} paper collages to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
