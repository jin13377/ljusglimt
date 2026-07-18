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
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

STOCKHOLM = ZoneInfo("Europe/Stockholm")
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
MEDIA_RSS_NAMESPACE = "http://search.yahoo.com/mrss/"
YOUTUBE_NAMESPACE = "http://www.youtube.com/xml/schemas/2015"
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
    r"\b(?:abandon(?:ed|ment)?|abuse|anxiety|assault|backlash|blood|bloody|bomb|chronic loneliness|closing|conflict|criticiz(?:e|ed|es|ing)|crush(?:ed|ing)?|death|desperat(?:e|ely)|distress(?:ed|ing)?|earthquake|extinct(?:ion)?|extremism|fraud|gasp(?:ing)?|harass(?:ment|ed|ing)?|harrowing|hooks? in|injur(?:ed|y|ies)|killed|loathe|locked away|lost (?:a |both |back )?legs?|mange|mangled|missing flipper|murder|onlyfans|revok(?:e|ed|es|ing)|scared|shooting|shocked|sick|stranded|strangl(?:e|ed|es|ing)|stroke|stuck in|terror|terrified|threaten(?:ed|ing)?|traffick(?:ing|ed)?|trap(?:ped)?|traumatized|treatment center|unable to move|violence|war|bomb|död(?:a|ade)?|jordbävning|katastrof|krig|mord|skjutning|terror|hotar|försvagade|övergrepp)\b",
    re.IGNORECASE,
)
FEED_NOISE_RE = re.compile(r"\b(?:appeared first on|share the stories)\b", re.IGNORECASE)
POSITIVE_CANDIDATE_RE = re.compile(
    r"\b(?:achiev(?:e|ed|ement)|adopt(?:ed|ion)?|adorable|award(?:ed|s)?|best friend|birth|breakthrough|celebrat(?:e|ed|es|ing|ion)|conservation(?:ist|ists)?|cuddl(?:e|ed|es|ing|y)|discov(?:er|ered|ery)|free(?:d|ing)?|friend(?:s|ship)?|help(?:s|ed|ing)?|hope(?:ful)?|improv(?:e|ed|ement)|innovation|kitten(?:s)?|lov(?:e|ed|es|ing)|milestone|play(?:s|ed|ing|ful)?|priceless|protect(?:s|ed|ing|ion)?|pupp(?:y|ies)|recover(?:ed|y)|rescu(?:e|ed|es|ing)|restor(?:e|ed|es|ing|ation)|save(?:d|s|ing)?|second chance|smooth(?:er|est)|solv(?:e|ed|es|ing)|spoil(?:s|ed|ing)?|success(?:ful)?|surpris(?:e|ed|es|ing)|together|treat(?:s|ed|ing)?|volunteer(?:s|ed|ing)?|win(?:s|ning)?|bevara|elev(?:er)?|firar|framsteg|förbättr(?:a|ar|ad|ats)|förebygg(?:a|er|ande)|glädje|hjälp(?:a|er|te)|hopp|innovation|lägre risk|lösning(?:ar)?|lovande|ny metod|ny teknik|rekord|räddad|samarbete|skydda|stärk(?:a|er|t)|anslag|beviljats|delaktighet|hållbar|initiativ|omställning|satsning|upptäckt|utbildning)\b",
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


def clean_source_description(value: str | None, video_policy: dict | None = None) -> str:
    text = value or ""
    if isinstance(video_policy, dict) and video_policy.get("provider") == "youtube":
        for marker in ("Love Animals? Subscribe:", "Follow The Dodo:", "Produced by", "Hosted by"):
            text = text.split(marker, 1)[0]
        text = re.sub(r"https?://\S+", " ", text)
    return clean_text(text)[:400]


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


def reusable_swedish_title(item: dict, previous: dict | None) -> dict:
    if not previous or previous.get("source_fingerprint") != item.get("source_fingerprint"):
        return {}
    raw_title = previous.get("display_title_sv")
    title = clean_text(raw_title)[:260] if isinstance(raw_title, str) else ""
    return {"display_title_sv": title} if title else {}


def curated_swedish_copy(item: dict, catalog: dict | None) -> dict:
    entries = catalog.get("items") if isinstance(catalog, dict) else None
    entry = entries.get(item.get("id")) if isinstance(entries, dict) else None
    if (not isinstance(entry, dict)
            or entry.get("source_fingerprint") != item.get("source_fingerprint")):
        return {}
    raw_title = entry.get("title")
    raw_summary = entry.get("summary")
    title = clean_text(raw_title)[:260] if isinstance(raw_title, str) else ""
    summary = clean_text(raw_summary)[:500] if isinstance(raw_summary, str) else ""
    if not title or not summary:
        return {}
    return {"display_title_sv": title, "agent_summary": summary}


def has_swedish_copy(item: dict) -> bool:
    language = str(item.get("language") or "und").casefold()
    if language == "sv" or language.startswith("sv-"):
        return True
    if not (language == "en" or language.startswith("en-")):
        return True
    title = item.get("display_title_sv")
    summary = item.get("agent_summary")
    return bool(isinstance(title, str) and clean_text(title)
                and isinstance(summary, str) and clean_text(summary))


def public_eligible(item: dict) -> bool:
    """Mirror the frontend's fetched-news suitability filter."""
    title = str(item.get("title") or "")
    excerpt = str(item.get("source_excerpt") or "")
    combined = f"{title} {excerpt}"
    return (has_swedish_copy(item)
            and not title.strip().endswith("?")
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
    """Return a strict, allowlisted image supplied by the source feed."""
    if not isinstance(image_policy, dict) or image_policy.get("enabled") is not True:
        return {}
    configured_hosts = image_policy.get("allowed_image_hosts")
    if not isinstance(configured_hosts, list) or not configured_hosts:
        return {}
    mode = image_policy.get("mode", "licensed")
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

    source_url = _safe_https_url(article_url)
    if not candidates or not source_url:
        return {}

    if mode == "feed-thumbnail":
        configured_article_hosts = image_policy.get("allowed_article_hosts")
        configured_credit = clean_text(image_policy.get("credit"))[:240]
        if not isinstance(configured_article_hosts, list) or not configured_credit:
            return {}
        allowed_article_hosts = {
            host.casefold() for host in configured_article_hosts
            if isinstance(host, str) and re.fullmatch(r"[a-z0-9.-]+", host.casefold())
        }
        article_host = (urllib.parse.urlsplit(source_url).hostname or "").casefold()
        if article_host not in allowed_article_hosts:
            return {}
        return {
            "source_image_verified": True,
            "source_image_url": candidates[0],
            "source_image_alt": media_titles[0] if media_titles else article_title,
            "source_image_credit": configured_credit,
            "source_image_rights_url": source_url,
            "source_image_creator": configured_credit,
            "source_image_source_url": source_url,
            "source_image_verification_method": "rss-syndicated-thumbnail-v1",
        }

    configured_licenses = image_policy.get("allowed_license_urls")
    if (not isinstance(configured_licenses, list) or not configured_licenses
            or any(not isinstance(url, str) or url not in ALLOWED_IMAGE_LICENSES
                   for url in configured_licenses)):
        return {}
    allowed_license_urls = set(configured_licenses)
    unique_licenses = set(licenses)
    if len(unique_licenses) != 1 or not credits:
        return {}
    license_url = next(iter(unique_licenses))
    license_id = ALLOWED_IMAGE_LICENSES.get(license_url)
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
    verification_method = previous.get("source_image_verification_method")
    if verification_method in {"rss-license-v1", "rss-syndicated-thumbnail-v1"}:
        reusable["source_image_verification_method"] = verification_method
    return reusable


def _video_policy_providers(video_policy: dict | None) -> set[str]:
    if not isinstance(video_policy, dict) or video_policy.get("enabled") is not True:
        return set()
    configured = video_policy.get("providers")
    if not isinstance(configured, list):
        configured = [video_policy.get("provider")]
    return {
        provider for provider in configured
        if isinstance(provider, str) and provider in {"youtube", "dailymotion"}
    }


def _supported_video_from_url(value: object, providers: set[str]) -> dict:
    safe_url = _safe_https_url(html.unescape(value) if isinstance(value, str) else value)
    if not safe_url:
        return {}
    parsed = urllib.parse.urlsplit(safe_url)
    host = (parsed.hostname or "").casefold()
    path_parts = [part for part in parsed.path.split("/") if part]

    if "youtube" in providers and host in {
        "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtube-nocookie.com",
    }:
        video_id = ""
        if host == "youtu.be" and path_parts:
            video_id = path_parts[0]
        elif path_parts and path_parts[0] in {"embed", "shorts", "live"} and len(path_parts) >= 2:
            video_id = path_parts[1]
        elif parsed.path.rstrip("/") == "/watch":
            video_id = urllib.parse.parse_qs(parsed.query).get("v", [""])[0]
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            return {
                "provider": "youtube",
                "video_id": video_id,
                "embed_url": f"https://www.youtube-nocookie.com/embed/{video_id}",
                "source_url": f"https://www.youtube.com/watch?v={video_id}",
            }

    if "dailymotion" in providers and host in {
        "dailymotion.com", "www.dailymotion.com", "geo.dailymotion.com", "dai.ly",
    }:
        video_id = ""
        if host == "dai.ly" and path_parts:
            video_id = path_parts[0]
        elif len(path_parts) >= 2 and path_parts[0] == "video":
            video_id = path_parts[1].split("_", 1)[0]
        elif host == "geo.dailymotion.com" and parsed.path.rstrip("/") == "/player.html":
            video_id = urllib.parse.parse_qs(parsed.query).get("video", [""])[0]
        if re.fullmatch(r"x[a-z0-9]+", video_id):
            return {
                "provider": "dailymotion",
                "video_id": video_id,
                "embed_url": f"https://geo.dailymotion.com/player.html?video={video_id}",
                "source_url": f"https://www.dailymotion.com/video/{video_id}",
            }
    return {}


def verified_source_video(node: ET.Element, article_url: str, article_title: str,
                          video_policy: dict | None) -> dict:
    """Accept only exact YouTube/Dailymotion IDs supplied by RSS/Atom metadata."""
    providers = _video_policy_providers(video_policy)
    if not providers:
        return {}
    candidates: dict[tuple[str, str], dict] = {}
    for child in node.iter():
        namespace, local = _tag_parts(child)
        if namespace == YOUTUBE_NAMESPACE and local == "videoid" and "youtube" in providers:
            video_id = (child.text or "").strip()
            if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
                candidates[("youtube", video_id)] = {
                    "provider": "youtube",
                    "video_id": video_id,
                    "embed_url": f"https://www.youtube-nocookie.com/embed/{video_id}",
                    "source_url": f"https://www.youtube.com/watch?v={video_id}",
                }

        mime = child.attrib.get("type", "").casefold()
        medium = child.attrib.get("medium", "").casefold()
        is_video_metadata = (
            (namespace == MEDIA_RSS_NAMESPACE and local in {"content", "player"}
             and (local == "player" or medium == "video" or mime.startswith("video/")))
            or (local == "enclosure" and mime.startswith("video/"))
        )
        if is_video_metadata:
            candidate = _supported_video_from_url(
                child.attrib.get("url") or child.attrib.get("href") or child.attrib.get("src"), providers)
            if candidate:
                candidates[(candidate["provider"], candidate["video_id"])] = candidate

        raw_text = html.unescape(child.text or "")
        if raw_text and ("youtube" in raw_text.casefold() or "youtu.be" in raw_text.casefold()
                         or "dailymotion" in raw_text.casefold() or "dai.ly" in raw_text.casefold()):
            for possible_url in re.findall(r"https://[^\s\"'<>]+", raw_text):
                candidate = _supported_video_from_url(possible_url.rstrip(".,);]"), providers)
                if candidate:
                    candidates[(candidate["provider"], candidate["video_id"])] = candidate

    if len(candidates) != 1 or not _safe_https_url(article_url):
        return {}
    video = next(iter(candidates.values()))
    video["title"] = article_title
    return {"source_video": video}


def reusable_source_video(item: dict, previous: dict | None) -> dict:
    if not previous or previous.get("source_fingerprint") != item.get("source_fingerprint"):
        return {}
    video = previous.get("source_video")
    if not isinstance(video, dict):
        return {}
    provider = video.get("provider")
    if provider not in {"youtube", "dailymotion"}:
        return {}
    normalized = _supported_video_from_url(video.get("source_url"), {provider})
    title = clean_text(video.get("title"))[:260]
    if (not normalized or normalized.get("video_id") != video.get("video_id")
            or normalized.get("embed_url") != video.get("embed_url") or not title):
        return {}
    normalized["title"] = title
    return {"source_video": normalized}


def parse_date(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    swedish_months = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
    }
    swedish_date = re.fullmatch(r"(\d{1,2})\s+([a-zåäö]{3})\s+(\d{4})", value.casefold())
    if swedish_date and swedish_date.group(2) in swedish_months:
        return datetime(
            int(swedish_date.group(3)), swedish_months[swedish_date.group(2)],
            int(swedish_date.group(1)), tzinfo=timezone.utc,
        ).isoformat().replace("+00:00", "Z")
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
        if local in names:
            text = "".join(child.itertext()).strip()
            if text:
                return text
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


def parse_feed(payload: bytes, source: str, language: str, image_policy: dict | None = None,
               video_policy: dict | None = None) -> list[dict]:
    root = ET.fromstring(payload)
    nodes = [n for n in root.iter() if n.tag.rsplit("}", 1)[-1].casefold() in ("item", "entry")]
    result = []
    for node in nodes:
        title = clean_text(first_text(node, ("title",)))[:260]
        link = canonical_url(entry_link(node))
        if not title or not link or len(link) > 1200 or urllib.parse.urlsplit(link).scheme != "https":
            continue
        # Keep only a short source-provided excerpt; the full article stays at source.
        description = clean_source_description(
            first_text(node, ("description", "summary", "content")), video_policy)
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
        item.update(verified_source_video(node, link, title, video_policy))
        result.append(item)
    return result


def parse_dailymotion_feed(payload: bytes, source: str, language: str,
                           image_policy: dict | None = None,
                           video_policy: dict | None = None) -> list[dict]:
    """Normalize The Dodo's public Dailymotion listing without an API key."""
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid Dailymotion JSON") from exc
    entries = document.get("list") if isinstance(document, dict) else None
    if not isinstance(entries, list):
        raise ValueError("Dailymotion response is missing its list")
    if (not isinstance(image_policy, dict) or image_policy.get("enabled") is not True
            or image_policy.get("mode") != "feed-thumbnail"
            or "dailymotion" not in _video_policy_providers(video_policy)):
        return []
    configured_image_hosts = image_policy.get("allowed_image_hosts")
    configured_article_hosts = image_policy.get("allowed_article_hosts")
    credit = clean_text(image_policy.get("credit"))[:240]
    if (not isinstance(configured_image_hosts, list) or not isinstance(configured_article_hosts, list)
            or not credit):
        return []
    image_hosts = {str(host).casefold() for host in configured_image_hosts}
    article_hosts = {str(host).casefold() for host in configured_article_hosts}

    result = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        video_id = str(entry.get("id") or "").strip()
        title = clean_text(entry.get("title"))[:260]
        link = _safe_https_url(entry.get("url"))
        image_url = _safe_https_url(entry.get("thumbnail_720_url"), image_hosts)
        if (not re.fullmatch(r"x[a-z0-9]+", video_id) or not title or not link or not image_url
                or (urllib.parse.urlsplit(link).hostname or "").casefold() not in article_hosts):
            continue
        published = None
        created_time = entry.get("created_time")
        if isinstance(created_time, int) and not isinstance(created_time, bool) and created_time > 0:
            try:
                published = datetime.fromtimestamp(created_time, timezone.utc).isoformat().replace("+00:00", "Z")
            except (OverflowError, OSError, ValueError):
                published = None
        description = clean_text(entry.get("description"))[:400]
        item = {
            "id": hashlib.sha256(canonical_url(link).encode("utf-8")).hexdigest()[:20],
            "title": title,
            "url": canonical_url(link),
            "source": source,
            "language": language,
            "published_at": published,
            "source_excerpt": description,
            "agent_summary": "",
            "source_image_verified": True,
            "source_image_url": image_url,
            "source_image_alt": title,
            "source_image_credit": credit,
            "source_image_rights_url": canonical_url(link),
            "source_image_creator": credit,
            "source_image_source_url": canonical_url(link),
            "source_image_verification_method": "dailymotion-api-thumbnail-v1",
            "source_video": {
                "provider": "dailymotion",
                "video_id": video_id,
                "embed_url": f"https://geo.dailymotion.com/player.html?video={video_id}",
                "source_url": canonical_url(link),
                "title": title,
            },
        }
        item["source_fingerprint"] = source_fingerprint(item)
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


def apply_language_mix(ranked: list[dict], limit: int, primary_language: str,
                       primary_share: float) -> list[dict]:
    """Keep a ranked feed near the configured original-source language mix."""
    if limit < 1:
        return []
    target_primary = min(limit, max(0, int(limit * primary_share + 0.5)))
    language = primary_language.casefold()
    primary = [item for item in ranked if str(item.get("language") or "und").casefold().startswith(language)]
    secondary = [item for item in ranked if item not in primary]
    selected = primary[:target_primary] + secondary[:limit - target_primary]
    if len(selected) < limit:
        selected_ids = {id(item) for item in selected}
        selected.extend(item for item in ranked if id(item) not in selected_ids)
    selected_ids = {id(item) for item in selected[:limit]}
    return [item for item in ranked if id(item) in selected_ids][:limit]


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
    request = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": "application/rss+xml, application/atom+xml, application/xml, application/json, text/xml"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        if urllib.parse.urlsplit(response.geturl()).scheme != "https":
            raise RuntimeError("feed redirected to a non-HTTPS URL")
        payload = response.read(5_000_001)
        if len(payload) > 5_000_000:
            raise RuntimeError("feed exceeds the 5 MB limit")
        return payload


def should_run(force: bool, scheduled: bool, now: datetime) -> bool:
    """Allow a scheduled job even when GitHub starts it after the target hour."""
    return force or scheduled or now.astimezone(STOCKHOLM).hour in {0, 12}


def publication_slot(now: datetime) -> str:
    local = now.astimezone(STOCKHOLM)
    slot_hour = 12 if local.hour >= 12 else 0
    return f"{local.date().isoformat()}T{slot_hour:02d}:00"


def is_within_max_age(item: dict, max_age_days: object, now: datetime) -> bool:
    if max_age_days is None:
        return True
    if type(max_age_days) is not int or max_age_days < 1:
        return False
    published = str(item.get("published_at") or "").strip()
    try:
        published_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
    except ValueError:
        return False
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    return published_at <= now and now - published_at.astimezone(timezone.utc) <= timedelta(days=max_age_days)


def main(argv: list[str] | None = None) -> int:
    base = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=base / "config/feeds.json")
    parser.add_argument("--output", type=Path, default=base / "data/news.json")
    parser.add_argument("--history", type=Path, default=base / "data/history.json")
    parser.add_argument("--translations", type=Path, default=base / "config/swedish-copy.json")
    parser.add_argument("--force", action="store_true", help="bypass the 00:00/12:00 Europe/Stockholm gate")
    parser.add_argument("--scheduled", action="store_true", help="run the current 00:00/12:00 slot even if the scheduler was delayed")
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    if not should_run(args.force, args.scheduled, now):
        print("Skip: local time in Europe/Stockholm is not 00:xx or 12:xx.")
        return 0

    config = load_json(args.config, {})
    translations = load_json(args.translations, {"items": {}})
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
            video_policy = feed.get("video_policy", config.get("video_policy"))
            if feed.get("format") == "dailymotion-json":
                parsed = parse_dailymotion_feed(payload, feed["name"], feed.get("language", "und"),
                                                 feed.get("image_policy"), video_policy)
            else:
                parsed = parse_feed(payload, feed["name"], feed.get("language", "und"),
                                    feed.get("image_policy"), video_policy)
            selected = []
            for item in parsed:
                if not is_within_max_age(item, feed.get("max_age_days"), now):
                    continue
                category = feed.get("category")
                if isinstance(category, str) and category.strip():
                    item["category"] = category.strip()[:80]
                if feed.get("require_source_image") is True and item.get("source_image_verified") is not True:
                    continue
                if feed.get("require_video") is True and not isinstance(item.get("source_video"), dict):
                    continue
                item["source_tier_bonus"] = int(feed.get("base_score", 0))
                item["source_item_limit"] = int(feed.get("max_items", config.get("max_items", 48)))
                selected.append(item)
            retained_limit = int(config.get("retain_localized_per_source", 6))
            selected_ids = {item.get("id") for item in selected}
            retained_count = 0
            for previous_item in old_items.values():
                if (retained_count >= retained_limit or previous_item.get("source") != feed.get("name")
                        or previous_item.get("id") in selected_ids or not has_swedish_copy(previous_item)
                        or not is_within_max_age(previous_item, feed.get("max_age_days"), now)):
                    continue
                retained = dict(previous_item)
                retained["source_tier_bonus"] = int(feed.get("base_score", 0))
                retained["source_item_limit"] = int(feed.get("max_items", config.get("max_items", 48)))
                selected.append(retained)
                retained_count += 1
            candidates.extend(selected)
        except Exception as exc:  # One broken third-party feed must not stop the others.
            source_name = feed.get("name", "Unknown")
            errors.append({"source": source_name, "error": str(exc)[:300]})
            # A temporary outage must not make an entire section disappear.
            # Keep the last published entries from that exact source until its
            # allowlisted feed succeeds again.
            for previous_item in old_items.values():
                if previous_item.get("source") != source_name:
                    continue
                retained = dict(previous_item)
                retained["source_tier_bonus"] = int(feed.get("base_score", 0))
                retained["source_item_limit"] = int(feed.get("max_items", config.get("max_items", 48)))
                candidates.append(retained)

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
        item.update(reusable_swedish_title(item, previous))
        item.update(curated_swedish_copy(item, translations))
        item["public_eligible"] = public_eligible(item)
        item.update(reusable_ai_image(item, previous))
        item.update(reusable_generated_image(item, previous))
        if not isinstance(item.get("source_video"), dict):
            item.update(reusable_source_video(item, previous))
        # Fresh, fully licensed feed metadata wins over any previous image.
        if item.get("source_image_verified") is not True:
            item.update(reusable_source_image(item, previous))
        unique[key] = item
        title_keys.add(title_key)

    ranked = sorted(unique.values(), key=lambda x: (
        bool(x.get("public_eligible")), x["positivity_score"], x.get("published_at") or ""
    ), reverse=True)
    source_capped = []
    source_counts: dict[str, int] = {}
    for item in ranked:
        source = item["source"]
        limit = item.pop("source_item_limit", int(config.get("max_items", 48)))
        if source_counts.get(source, 0) >= limit:
            continue
        source_counts[source] = source_counts.get(source, 0) + 1
        source_capped.append(item)

    max_items = int(config.get("max_items", 48))
    language_mix = config.get("language_mix")
    if isinstance(language_mix, dict) and language_mix.get("enabled") is True:
        items = apply_language_mix(
            source_capped,
            max_items,
            str(language_mix.get("primary_language", "sv")),
            float(language_mix.get("primary_share", 0.70)),
        )
    else:
        items = source_capped[:max_items]
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
