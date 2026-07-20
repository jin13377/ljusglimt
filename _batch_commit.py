#!/usr/bin/env python3
"""Commit Z-Image-Turbo article images in CI-safe batches of 3.

Rebuilds data/news.json for each batch so that ONLY the 3 target articles differ
from HEAD (others kept identical to HEAD), then commits the 3 webp files +
news.json. CI validator allows <=3 changed articles per commit.
"""
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).parent
NEWS = ROOT / "data" / "news.json"
TARGET = ROOT / "_target_news.json"
ART = ROOT / "public" / "news-images" / "ai" / "articles"

ids = json.loads((ROOT / "_batch_ids.json").read_text()) if (ROOT / "_batch_ids.json").exists() else None
batch_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
BATCH = 3

head_raw = subprocess.run(["git", "show", "HEAD:data/news.json"], cwd=ROOT,
                          capture_output=True, text=True).check_returncode() or None
head = json.loads(subprocess.run(["git", "show", "HEAD:data/news.json"], cwd=ROOT,
                                  capture_output=True, text=True).stdout)
target = json.loads(TARGET.read_text(encoding="utf-8"))

if ids is None:
    # compute changed ids (differ from head)
    head_by = {i["id"]: i for i in head["items"]}
    ids = [i["id"] for i in target["items"]
           if i["id"] not in head_by or head_by[i["id"]].get("ai_image") != i.get("ai_image")]
    (ROOT / "_batch_ids.json").write_text(json.dumps(ids))

start = batch_idx * BATCH
chunk = ids[start:start + BATCH]
if not chunk:
    print("INGA FLER BATCHER")
    raise SystemExit

# Build a news.json with HEAD values except for the chunk
head_by = {i["id"]: i for i in head["items"]}
tgt_by = {i["id"]: i for i in target["items"]}
out_items = []
for i in head["items"]:
    if i["id"] in chunk:
        out_items.append(tgt_by[i["id"]])
    else:
        out_items.append(i)
out = {k: v for k, v in target.items() if k != "items"}
out["items"] = out_items
NEWS.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

# Stage 3 webp + news.json
files = ["data/news.json"]
for cid in chunk:
    fp = tgt_by[cid]["ai_image"]["url"].split("/")[-1]
    files.append(str(ART / fp))
subprocess.run(["git", "add", *files], cwd=ROOT, check=True)
msg = f"feat(images): Z-Image-Turbo illustrations (batch {batch_idx+1}, {len(chunk)} imgs)"
subprocess.run(["git", "commit", "-m", msg], cwd=ROOT, check=True)
print(f"Commit {batch_idx+1}: {chunk}")
print(f"Kvar: {max(0, len(ids)-(start+BATCH))} artiklar")
