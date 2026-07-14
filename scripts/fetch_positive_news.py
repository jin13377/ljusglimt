#!/usr/bin/env python3
"""Fetch, rank and atomically publish positive RSS/Atom news.

Standard-library only. The script never generates factual claims: it copies
source metadata and leaves agent_summary empty for an optional later step.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import tempfile
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

STOCKHOLM = ZoneInfo("Europe/Stockholm")
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
WORD_RE = re.compile(r"[^\wåäö]+", re.IGNORECASE)


def clean_text(value: str | None) -> str:
    value = html.unescape(value or "")
    value = TAG_RE.sub(" ", value)
    return SPACE_RE.sub(" ", value).strip()


def normalize_title(value: str) -> str:
    return WORD_RE.sub(" ", value.casefold()).strip()


def canonical_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value.strip())
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [(k, v) for k, v in query if not k.casefold().startswith("utm_")]
    return urllib.parse.urlunsplit(
        (parsed.scheme.casefold(), parsed.netloc.casefold(), parsed.path.rstrip("/"),
         urllib.parse.urlencode(query), "")
    )


def parse_date(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def first_text(node: ET.Element, names: tuple[str, ...]) -> str:
    for child in node.iter():
        local = child.tag.rsplit("}", 1)[-1].casefold()
        if local in names and child.text:
            return child.text
    return ""


def entry_link(node: ET.Element) -> str:
    # Atom uses <link href="...">; RSS normally stores text in <link>.
    for child in node.iter():
        if child.tag.rsplit("}", 1)[-1].casefold() == "link":
            href = child.attrib.get("href", "").strip()
            rel = child.attrib.get("rel", "alternate")
            if href and rel in ("alternate", ""):
                return href
            if child.text and child.text.strip():
                return child.text.strip()
    return ""


def parse_feed(payload: bytes, source: str, language: str) -> list[dict]:
    root = ET.fromstring(payload)
    nodes = [n for n in root.iter() if n.tag.rsplit("}", 1)[-1].casefold() in ("item", "entry")]
    result = []
    for node in nodes:
        title = clean_text(first_text(node, ("title",)))
        link = canonical_url(entry_link(node))
        if not title or not link or urllib.parse.urlsplit(link).scheme not in ("http", "https"):
            continue
        # Keep only a short source-provided excerpt; the full article stays at source.
        description = clean_text(first_text(node, ("description", "summary", "content")))[:400]
        published = parse_date(first_text(node, ("pubdate", "published", "updated", "date")))
        stable = link or normalize_title(title)
        result.append({
            "id": hashlib.sha256(stable.encode("utf-8")).hexdigest()[:20],
            "title": title,
            "url": link,
            "source": source,
            "language": language,
            "published_at": published,
            "source_excerpt": description,
            "agent_summary": "",
        })
    return result


def score_item(item: dict, positive: list[str], blocked: list[str]) -> tuple[int, list[str]]:
    haystack = f"{item['title']} {item['source_excerpt']}".casefold()
    blocked_hits = sorted({word for word in blocked if word.casefold() in haystack})
    if blocked_hits:
        return -100, [f"blocked:{word}" for word in blocked_hits]
    hits = sorted({word for word in positive if word.casefold() in haystack})
    # Rubric is intentionally transparent and conservative.
    title = item["title"].casefold()
    score = len(hits) + sum(1 for word in hits if word.casefold() in title)
    return score, hits


def atomic_json_write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
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


def load_json(path: Path, default: object) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def fetch(url: str, timeout: int, user_agent: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        return response.read(5_000_000)


def should_run(force: bool, now: datetime) -> bool:
    return force or now.astimezone(STOCKHOLM).hour == 2


def main(argv: list[str] | None = None) -> int:
    base = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=base / "config/feeds.json")
    parser.add_argument("--output", type=Path, default=base / "data/news.json")
    parser.add_argument("--history", type=Path, default=base / "data/history.json")
    parser.add_argument("--force", action="store_true", help="bypass the 02:00 Europe/Stockholm gate")
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    if not should_run(args.force, now):
        print("Skip: local time in Europe/Stockholm is not 02:xx.")
        return 0

    config = load_json(args.config, {})
    if not isinstance(config, dict) or not config.get("feeds"):
        print(f"Invalid or empty config: {args.config}", file=sys.stderr)
        return 2

    old_output = load_json(args.output, {"items": []})
    old_summaries = {
        item.get("id"): item.get("agent_summary", "")
        for item in old_output.get("items", [])
        if isinstance(item, dict) and item.get("id")
    } if isinstance(old_output, dict) else {}
    history = load_json(args.history, {"seen_ids": []})
    seen_ids = set(history.get("seen_ids", [])) if isinstance(history, dict) else set()

    candidates: list[dict] = []
    errors: list[dict] = []
    for feed in config["feeds"]:
        if not feed.get("enabled", True):
            continue
        try:
            payload = fetch(feed["url"], int(config.get("request_timeout_seconds", 20)), config.get("user_agent", "GladnyttBot/1.0"))
            candidates.extend(parse_feed(payload, feed["name"], feed.get("language", "und")))
        except Exception as exc:  # One broken third-party feed must not stop the others.
            errors.append({"source": feed.get("name", "Unknown"), "error": str(exc)[:300]})

    unique: dict[str, dict] = {}
    title_keys: set[str] = set()
    for item in candidates:
        key = canonical_url(item["url"])
        title_key = normalize_title(item["title"])
        if key in unique or title_key in title_keys:
            continue
        score, reasons = score_item(item, config.get("positive_keywords", []), config.get("blocked_keywords", []))
        if score < int(config.get("minimum_score", 2)):
            continue
        item["positivity_score"] = score
        item["positive_signals"] = reasons
        item["agent_summary"] = old_summaries.get(item["id"], "")
        unique[key] = item
        title_keys.add(title_key)

    items = sorted(unique.values(), key=lambda x: (x["positivity_score"], x.get("published_at") or ""), reverse=True)
    items = items[: int(config.get("max_items", 24))]
    new_ids = [item["id"] for item in items if item["id"] not in seen_ids]
    seen_ids.update(item["id"] for item in items)

    output = {
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "timezone": "Europe/Stockholm",
        "disclaimer": "Rubriker och utdrag kommer från angivna källor. Agent-sammanfattningar ska faktagranskas mot källänken.",
        "new_item_ids": new_ids,
        "fetch_errors": errors,
        "items": items,
    }
    atomic_json_write(args.output, output)
    atomic_json_write(args.history, {"updated_at": output["generated_at"], "seen_ids": sorted(seen_ids)[-5000:]})
    print(f"Published {len(items)} items ({len(new_ids)} new); {len(errors)} feed errors.")
    return 0 if items or not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
