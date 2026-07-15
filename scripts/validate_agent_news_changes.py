#!/usr/bin/env python3
"""Verify that an agent changed summaries only, never imported source facts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate_news_changes(before: dict, after: dict) -> None:
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ValueError("news documents must be JSON objects")

    before_meta = {key: value for key, value in before.items() if key != "items"}
    after_meta = {key: value for key, value in after.items() if key != "items"}
    if before_meta != after_meta:
        raise ValueError("top-level source metadata changed")

    before_items = before.get("items")
    after_items = after.get("items")
    if not isinstance(before_items, list) or not isinstance(after_items, list):
        raise ValueError("items must be arrays")
    if len(before_items) != len(after_items):
        raise ValueError("articles were added or removed")

    for index, (old, new) in enumerate(zip(before_items, after_items, strict=True)):
        if not isinstance(old, dict) or not isinstance(new, dict):
            raise ValueError(f"item {index} must be an object")
        article_id = old.get("id") or f"index {index}"
        old_source = {key: value for key, value in old.items() if key != "agent_summary"}
        new_source = {key: value for key, value in new.items() if key != "agent_summary"}
        if old_source != new_source:
            raise ValueError(f"source fields changed for {article_id}")

        old_summary = old.get("agent_summary", "")
        new_summary = new.get("agent_summary", "")
        if not isinstance(new_summary, str):
            raise ValueError(f"agent_summary for {article_id} must be a string")
        if len(new_summary) > 500:
            raise ValueError(f"agent_summary for {article_id} exceeds 500 characters")
        if old_summary and new_summary != old_summary:
            raise ValueError(f"an existing summary changed for {article_id}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    args = parser.parse_args()
    before = json.loads(args.before.read_text(encoding="utf-8"))
    after = json.loads(args.after.read_text(encoding="utf-8"))
    validate_news_changes(before, after)
    print("Validated: the agent changed summary fields only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
