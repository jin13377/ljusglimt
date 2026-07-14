#!/usr/bin/env python3
"""Apply ID-keyed agent drafts without allowing changes to source facts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fetch_positive_news import atomic_json_write


def apply_summaries(news: dict, drafts: dict) -> tuple[dict, int]:
    summaries = drafts.get("summaries", {})
    if not isinstance(summaries, dict):
        raise ValueError("summaries must be an object keyed by article id")
    count = 0
    for item in news.get("items", []):
        article_id = item.get("id")
        if article_id not in summaries:
            continue
        summary = summaries[article_id]
        if not isinstance(summary, str):
            raise ValueError(f"summary for {article_id} must be a string")
        summary = " ".join(summary.split()).strip()
        if len(summary) > 500:
            raise ValueError(f"summary for {article_id} exceeds 500 characters")
        item["agent_summary"] = summary
        count += 1
    return news, count


def main() -> int:
    base = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--news", type=Path, default=base / "data/news.json")
    parser.add_argument("--drafts", type=Path, default=base / "data/summaries.pending.json")
    args = parser.parse_args()
    news = json.loads(args.news.read_text(encoding="utf-8"))
    drafts = json.loads(args.drafts.read_text(encoding="utf-8"))
    updated, count = apply_summaries(news, drafts)
    atomic_json_write(args.news, updated)
    print(f"Applied {count} agent summaries; source fields were unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
