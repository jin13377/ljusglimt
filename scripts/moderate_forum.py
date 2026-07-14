#!/usr/bin/env python3
"""Lista eller godkänn väntande foruminlägg."""

import argparse
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "forum.json"


def save(data):
    fd, name = tempfile.mkstemp(prefix="forum", suffix=".tmp", dir=PATH.parent)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(name, PATH)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--approve", help="ID för tråd eller svar som ska publiceras")
    parser.add_argument("--reject", help="ID för tråd eller svar som ska avslås")
    args = parser.parse_args()
    data = json.loads(PATH.read_text(encoding="utf-8"))
    found = False
    for topic in data.get("topics", []):
        items = [topic, *topic.get("replies", [])]
        for item in items:
            if item.get("status") == "pending" and not (args.approve or args.reject):
                print(f"{item['id']} | {item.get('author')} | {item.get('title', item.get('body', '')[:70])}")
            if item.get("id") == args.approve:
                item["status"] = "published"
                found = True
            if item.get("id") == args.reject:
                item["status"] = "rejected"
                found = True
    if args.approve or args.reject:
        if not found:
            raise SystemExit("ID hittades inte.")
        save(data)
        print("Modereringen sparades.")


if __name__ == "__main__":
    main()
