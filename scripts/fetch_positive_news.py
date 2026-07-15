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
MEDIA_RSS_NAMESPACE = "http://search.yahoo.com/mrss/"
CC_RSS_NAMESPACES = {
    MEDIA_RSS_NAMESPACE,
    "http://backend.userland.com/creativeCommonsRssModule",
    "http://creativecommons.org/ns#",
}
DC_CREATOR_NAMESPACES = {
    "http://purl.org/dc/elements/1.1/",
    "http://purl.org/dc/terms/",
}
ALLOWED_IMAGE_LICENSES = {
    "https://creativecommons.org/publicdomain/zero/1.0/": "CC0-1.0",
    "https://creativecommons.org/licenses/by/4.0/": "CC-BY-4.0",
}
SENSITIVE_CANDIDATE_RE = re.compile(
    r"\b(?:abandon(?:ed|ment)?|abuse|anxiety|assault|backlash|blood|bloody|bomb|chronic loneliness|closing|conflict|criticiz(?:e|ed|es|ing)|crush(?:ed|ing)?|death|desperat(?:e|ely)|distress(?:ed|ing)?|earthquake|extinct(?:ion)?|extremism|fraud|harass(?:ment|ed|ing)?|harrowing|hooks? in|injur(?:ed|y|ies)|killed|loathe|mangled|missing flipper|murder|onlyfans|revok(?:e|ed|es|ing)|shooting|shocked|stranded|strangl(?:e|ed|es|ing)|stroke|terror|threaten(?:ed|ing)?|traffick(?:ing|ed)?|trap(?:ped)?|treatment center|unable to move|violence|war)\b",
    re.IGNORECASE,
)
FEED_NOISE_RE = re.compile(r"\b(?:appeared first on|share the stories)\b", re.IGNORECASE)
POSITIVE_CANDIDATE_RE = re.compile(
    r"\b(?:achiev(?:e|ed|ement)|award(?:ed|s)?|birth|breakthrough|celebrat(?:e|ed|es|ing|ion)|conservation(?:ist|ists)?|discov(?:er|ered|ery)|free(?:d|ing)?|help(?:s|ed|ing)?|hope(?:ful)?|improv(?:e|ed|ement)|milestone|protect(?:s|ed|ing|ion)?|recover(?:ed|y)|rescu(?:e|ed|es|ing)|restor(?:e|ed|es|ing|ation)|save(?:d|s|ing)?|second chance|smooth(?:er|est)|solv(?:e|ed|es|ing)|success(?:ful)?|volunteer(?:s|ed|ing)?|win(?:s|ning)?)\b",
    re.IGNORECASE,
)
AI_IMAGE_KEYS = {
    "url", "alt", "model", "prompt_version", "source_fingerprint",
    "width", "height", "sha256", "generated_at",
}
GENERATED_IMAGE_KEYS = {
    "url", "alt", "style_version", "source_fingerprint",
    "width", "height", "sha256",
}
HEX_20_RE = re.compile(r"^[0-9a-f]{20}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ISO_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")
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


def source_fingerprint(item: dict) -> str:
    source_text = "\n".join(str(item.get(key) or "") for key in ("title", "source_excerpt", "published_at"))
    return hashlib.sha256(source_text.encode("utf-8")).hexdigest()[:20]


def reusable_summary(item: dict, previous: dict | None) -> str:
    if not previous or previous.get("source_fingerprint") != item.get("source_fingerprint"):
        return ""
    summary = previous.get("agent_summary", "")
    return summary if isinstance(summary, str) else ""


def public_eligible(item: dict) -> bool:
    """Mirror the frontend's fetched-news suitability filter."""
    title = str(item.get("title") or "")
    summary = item.get("agent_summary")
    excerpt = summary.strip() if isinstance(summary, str) and summary.strip() else str(item.get("source_excerpt") or "")
    combined = f"{title} {excerpt}"
    return (not title.strip().endswith("?")
            and not SENSITIVE_CANDIDATE_RE.search(combined)
            and not FEED_NOISE_RE.search(excerpt)
            and bool(POSITIVE_CANDIDATE_RE.search(combined)))


def reusable_ai_image(item: dict, previous: dict | None) -> dict:
    """Keep a generated image only when its complete nested schema is intact."""
    fingerprint = str(item.get("source_fingerprint") or "")
    article_id = str(item.get("id") or "")
    if (not previous or previous.get("source_fingerprint") != fingerprint
            or not HEX_20_RE.fullmatch(article_id) or not HEX_20_RE.fullmatch(fingerprint)):
        return {}
    image = previous.get("ai_image")
    if not isinstance(image, dict) or set(image) != AI_IMAGE_KEYS:
        return {}
    expected_url = f"/news-images/ai/articles/{article_id}-{fingerprint[:8]}-v1.webp"
    alt = image.get("alt")
    generated_at = image.get("generated_at")
    if (image.get("url") != expected_url
            or not isinstance(alt, str) or not alt.strip() or len(alt) > 400 or clean_text(alt) != alt
            or image.get("model") != "gpt-image-2"
            or image.get("prompt_version") != "editorial-concept-v1"
            or image.get("source_fingerprint") != fingerprint
            or type(image.get("width")) is not int or image.get("width") != 1280
            or type(image.get("height")) is not int or image.get("height") != 848
            or not isinstance(image.get("sha256"), str) or not SHA256_RE.fullmatch(image["sha256"])
            or not isinstance(generated_at, str) or not ISO_UTC_RE.fullmatch(generated_at)):
        return {}
    try:
        datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError:
        return {}
    return {"ai_image": dict(image)}


def reusable_generated_image(item: dict, previous: dict | None) -> dict:
    """Keep a free local illustration only while its source fingerprint matches."""
    if not previous or previous.get("source_fingerprint") != item.get("source_fingerprint"):
        return {}
    article_id = str(item.get("id") or "")
    fingerprint = str(item.get("source_fingerprint") or "")
    image = previous.get("generated_image")
    if (not HEX_20_RE.fullmatch(article_id) or not HEX_20_RE.fullmatch(fingerprint)
            or not isinstance(image, dict) or set(image) != GENERATED_IMAGE_KEYS):
        return {}
    expected_url = f"/news-images/generated/{article_id}-{fingerprint[:8]}-v1.svg"
    if (image.get("url") != expected_url
            or image.get("alt") != "Automatiskt skapad redaktionell illustration."
            or image.get("style_version") != "glimt-abstract-v1"
            or image.get("source_fingerprint") != fingerprint
            or image.get("width") != 1280 or image.get("height") != 848
            or not isinstance(image.get("sha256"), str)
            or not SHA256_RE.fullmatch(image["sha256"])):
        return {}
    return {"generated_image": dict(image)}


def _safe_https_url(value: object, allowed_hosts: set[str] | None = None) -> str:
    if not isinstance(value, str) or len(value.strip()) > 1200:
        return ""
    value = value.strip()
    try:
        parsed = urllib.parse.urlsplit(value)
        port = parsed.port
    except ValueError:
        return ""
    hostname = (parsed.hostname or "").casefold()
    if (parsed.scheme.casefold() != "https" or not hostname or parsed.username or parsed.password
            or port not in (None, 443)):
        return ""
    if allowed_hosts is not None and hostname not in allowed_hosts:
        return ""
    return value


def _tag_parts(node: ET.Element) -> tuple[str, str]:
    if node.tag.startswith("{") and "}" in node.tag:
        namespace, local = node.tag[1:].split("}", 1)
        return namespace, local.casefold()
    return "", node.tag.casefold()


def verified_rss_source_image(node: ET.Element, article_url: str, article_title: str,
                              image_policy: dict | None) -> dict:
    """Return displayable source metadata only for explicitly licensed media."""
    if not isinstance(image_policy, dict) or image_policy.get("enabled") is not True:
        return {}
    configured_hosts = image_policy.get("allowed_image_hosts")
    if not isinstance(configured_hosts, list) or not configured_hosts:
        return {}
    configured_licenses = image_policy.get("allowed_license_urls")
    if (not isinstance(configured_licenses, list) or not configured_licenses
            or any(not isinstance(url, str) or url not in ALLOWED_IMAGE_LICENSES
                   for url in configured_licenses)):
        return {}
    allowed_license_urls = set(configured_licenses)
    allowed_hosts = {
        host.casefold() for host in configured_hosts
        if isinstance(host, str) and re.fullmatch(r"[a-z0-9.-]+", host.casefold())
        and not host.startswith(".") and not host.endswith(".")
    }
    if not allowed_hosts:
        return {}

    licenses = []
    credits = []
    media_titles = []
    candidates = []
    for child in node.iter():
        namespace, local = _tag_parts(child)
        if local == "license" and namespace in CC_RSS_NAMESPACES:
            license_url = (child.attrib.get("href") or child.attrib.get("url") or child.text or "").strip()
            if license_url:
                licenses.append(license_url)
        elif ((local == "credit" and namespace == MEDIA_RSS_NAMESPACE)
              or (local == "creator" and namespace in DC_CREATOR_NAMESPACES)):
            credit = clean_text(child.text)[:240]
            if credit and credit not in credits:
                credits.append(credit)
        elif local == "title" and namespace == MEDIA_RSS_NAMESPACE:
            media_title = clean_text(child.text)[:400]
            if media_title:
                media_titles.append(media_title)

        if namespace != MEDIA_RSS_NAMESPACE:
            continue
        candidate_url = ""
        if local == "content":
            medium = child.attrib.get("medium", "").casefold()
            mime = child.attrib.get("type", "").casefold()
            if medium == "image" or mime.startswith("image/"):
                candidate_url = child.attrib.get("url", "")
        elif local == "thumbnail":
            candidate_url = child.attrib.get("url", "")
        candidate_url = _safe_https_url(candidate_url, allowed_hosts)
        if candidate_url and candidate_url not in candidates:
            candidates.append(candidate_url)

    unique_licenses = set(licenses)
    if len(unique_licenses) != 1 or not candidates or not credits:
        return {}
    license_url = next(iter(unique_licenses))
    license_id = ALLOWED_IMAGE_LICENSES.get(license_url)
    source_url = _safe_https_url(article_url)
    if not license_id or license_url not in allowed_license_urls or not source_url:
        return {}
    creator = " · ".join(credits)[:240]
    return {
        "source_image_verified": True,
        "source_image_url": candidates[0],
        "source_image_alt": media_titles[0] if media_titles else article_title,
        "source_image_credit": creator,
        "source_image_rights_url": license_url,
        "source_image_creator": creator,
        "source_image_license_id": license_id,
        "source_image_license_url": license_url,
        "source_image_source_url": source_url,
        "source_image_verification_method": "rss-license-v1",
    }


def reusable_source_image(item: dict, previous: dict | None) -> dict:
    if not previous or previous.get("source_fingerprint") != item.get("source_fingerprint"):
        return {}
    image_url = str(previous.get("source_image_url") or "").strip()
    rights_url = str(previous.get("source_image_rights_url") or "").strip()
    credit = clean_text(previous.get("source_image_credit"))[:240]
    image_parts = urllib.parse.urlsplit(image_url)
    rights_parts = urllib.parse.urlsplit(rights_url)
    if (previous.get("source_image_verified") is not True or not credit
            or image_parts.scheme != "https" or not image_parts.netloc
            or image_parts.username or image_parts.password
            or rights_parts.scheme != "https" or not rights_parts.netloc
            or rights_parts.username or rights_parts.password):
        return {}
    reusable = {
        "source_image_verified": True,
        "source_image_url": image_url[:1200],
        "source_image_alt": clean_text(previous.get("source_image_alt"))[:400],
        "source_image_credit": credit,
        "source_image_rights_url": rights_url[:1200],
    }
    license_url = _safe_https_url(previous.get("source_image_license_url"))
    source_url = _safe_https_url(previous.get("source_image_source_url"))
    license_id = previous.get("source_image_license_id")
    creator = clean_text(previous.get("source_image_creator"))[:240]
    if license_url in ALLOWED_IMAGE_LICENSES and license_id == ALLOWED_IMAGE_LICENSES[license_url]:
        reusable.update({"source_image_license_id": license_id, "source_image_license_url": license_url})
    if source_url:
        reusable["source_image_source_url"] = source_url
    if creator:
        reusable["source_image_creator"] = creator
    if previous.get("source_image_verification_method") == "rss-license-v1":
        reusable["source_image_verification_method"] = "rss-license-v1"
    return reusable


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


def parse_feed(payload: bytes, source: str, language: str, image_policy: dict | None = None) -> list[dict]:
    root = ET.fromstring(payload)
    nodes = [n for n in root.iter() if n.tag.rsplit("}", 1)[-1].casefold() in ("item", "entry")]
    result = []
    for node in nodes:
        title = clean_text(first_text(node, ("title",)))[:260]
        link = canonical_url(entry_link(node))
        if not title or not link or len(link) > 1200 or urllib.parse.urlsplit(link).scheme != "https":
            continue
        # Keep only a short source-provided excerpt; the full article stays at source.
        description = clean_text(first_text(node, ("description", "summary", "content")))[:400]
        published = parse_date(first_text(node, ("pubdate", "published", "updated", "date")))
        stable = link or normalize_title(title)
        item = {
            "id": hashlib.sha256(stable.encode("utf-8")).hexdigest()[:20],
            "title": title,
            "url": link,
            "source": source,
            "language": language,
            "published_at": published,
            "source_excerpt": description,
            "agent_summary": "",
        }
        item["source_fingerprint"] = source_fingerprint(item)
        item.update(verified_rss_source_image(node, link, title, image_policy))
        result.append(item)
    return result


def score_item(item: dict, positive: list[str], blocked: list[str]) -> tuple[int, list[str]]:
    haystack = f"{item['title']} {item['source_excerpt']}".casefold()
    blocked_hits = sorted({word for word in blocked if re.search(
        rf"(?<!\w){re.escape(word.casefold().strip())}(?:s|es)?(?!\w)", haystack
    )})
    if blocked_hits:
        return -100, [f"blocked:{word}" for word in blocked_hits]
    hits = sorted({word for word in positive if word.casefold() in haystack})
    # Rubric is intentionally transparent and conservative.
    title = item["title"].casefold()
    source_bonus = int(item.get("source_tier_bonus", 0))
    score = (source_bonus if hits else 0) + len(hits) + sum(1 for word in hits if word.casefold() in title)
    reasons = (["curated-positive-source"] if source_bonus else []) + hits
    return score, reasons


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
        if urllib.parse.urlsplit(response.geturl()).scheme != "https":
            raise RuntimeError("feed redirected to a non-HTTPS URL")
        payload = response.read(5_000_001)
        if len(payload) > 5_000_000:
            raise RuntimeError("feed exceeds the 5 MB limit")
        return payload


def should_run(force: bool, now: datetime) -> bool:
    return force or now.astimezone(STOCKHOLM).hour in {0, 12}


def publication_slot(now: datetime) -> str:
    local = now.astimezone(STOCKHOLM)
    slot_hour = 12 if local.hour >= 12 else 0
    return f"{local.date().isoformat()}T{slot_hour:02d}:00"


def main(argv: list[str] | None = None) -> int:
    base = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=base / "config/feeds.json")
    parser.add_argument("--output", type=Path, default=base / "data/news.json")
    parser.add_argument("--history", type=Path, default=base / "data/history.json")
    parser.add_argument("--force", action="store_true", help="bypass the 00:00/12:00 Europe/Stockholm gate")
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    if not should_run(args.force, now):
        print("Skip: local time in Europe/Stockholm is not 00:xx or 12:xx.")
        return 0

    config = load_json(args.config, {})
    if not isinstance(config, dict) or not config.get("feeds"):
        print(f"Invalid or empty config: {args.config}", file=sys.stderr)
        return 2

    old_output = load_json(args.output, {"items": []})
    old_items = {
        item.get("id"): item
        for item in old_output.get("items", [])
        if isinstance(item, dict) and item.get("id")
    } if isinstance(old_output, dict) else {}
    history = load_json(args.history, {"seen_ids": []})
    local_date = now.astimezone(STOCKHOLM).date().isoformat()
    local_slot = publication_slot(now)
    if not args.force and isinstance(history, dict) and history.get("last_successful_local_slot") == local_slot:
        print(f"Skip: news has already been published for {local_slot} Europe/Stockholm.")
        return 0
    history_ids = history.get("seen_ids", []) if isinstance(history, dict) else []
    ordered_seen = list(dict.fromkeys(item for item in history_ids if isinstance(item, str)))
    seen_ids = set(ordered_seen)

    candidates: list[dict] = []
    errors: list[dict] = []
    for feed in config["feeds"]:
        if not feed.get("enabled", True):
            continue
        try:
            payload = fetch(feed["url"], int(config.get("request_timeout_seconds", 20)), config.get("user_agent", "GladnyttBot/1.0"))
            parsed = parse_feed(payload, feed["name"], feed.get("language", "und"), feed.get("image_policy"))
            for item in parsed:
                item["source_tier_bonus"] = int(feed.get("base_score", 0))
                item["source_item_limit"] = int(feed.get("max_items", config.get("max_items", 48)))
            candidates.extend(parsed)
        except Exception as exc:  # One broken third-party feed must not stop the others.
            errors.append({"source": feed.get("name", "Unknown"), "error": str(exc)[:300]})

    if errors and not candidates:
        print(f"Fetch failed for every usable feed; keeping {args.output} unchanged.", file=sys.stderr)
        return 1

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
        previous = old_items.get(item["id"])
        item["agent_summary"] = reusable_summary(item, previous)
        item["public_eligible"] = public_eligible(item)
        item.update(reusable_ai_image(item, previous))
        item.update(reusable_generated_image(item, previous))
        # Fresh, fully licensed feed metadata wins over any previous image.
        if item.get("source_image_verified") is not True:
            item.update(reusable_source_image(item, previous))
        unique[key] = item
        title_keys.add(title_key)

    ranked = sorted(unique.values(), key=lambda x: (x["positivity_score"], x.get("published_at") or ""), reverse=True)
    items = []
    source_counts: dict[str, int] = {}
    for item in ranked:
        source = item["source"]
        limit = item.pop("source_item_limit", int(config.get("max_items", 48)))
        if source_counts.get(source, 0) >= limit:
            continue
        source_counts[source] = source_counts.get(source, 0) + 1
        items.append(item)
        if len(items) >= int(config.get("max_items", 48)):
            break
    new_ids = [item["id"] for item in items if item["id"] not in seen_ids]
    for item in items:
        if item["id"] not in seen_ids:
            ordered_seen.append(item["id"])
            seen_ids.add(item["id"])

    output = {
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "timezone": "Europe/Stockholm",
        "disclaimer": "Rubriker och utdrag kommer från angivna källor. Agent-sammanfattningar ska faktagranskas mot källänken.",
        "new_item_ids": new_ids,
        "fetch_errors": errors,
        "items": items,
    }
    atomic_json_write(args.output, output)
    atomic_json_write(args.history, {"updated_at": output["generated_at"], "last_successful_local_date": local_date,
                                     "last_successful_local_slot": local_slot,
                                     "seen_ids": ordered_seen[-5000:]})
    print(f"Published {len(items)} items ({len(new_ids)} new); {len(errors)} feed errors.")
    return 0 if items or not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
