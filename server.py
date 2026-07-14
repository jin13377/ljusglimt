#!/usr/bin/env python3
"""Glimt Nyheter: liten lokal webbserver och modererat forum-API."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
FORUM_FILE = DATA / "forum.json"
NEWS_FILE = DATA / "news.json"
PUBLIC_PAGES = {"index.html", "forum.html", "om.html", "404.html"}
PUBLIC_DATA = {"data/news.json", "data/seed-news.json"}
MAX_BODY = 24_000
RATE_LIMIT_SECONDS = 20
_last_post: dict[str, float] = {}
_rate_lock = threading.Lock()


def read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def atomic_write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def clean_text(value, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def visible_forum():
    payload = read_json(FORUM_FILE, {"topics": []})
    topics = []
    for topic in payload.get("topics", []):
        if topic.get("status") != "published":
            continue
        item = dict(topic)
        item["replies"] = [
            reply for reply in topic.get("replies", []) if reply.get("status") == "published"
        ]
        topics.append(item)
    return {"topics": topics}


class Handler(BaseHTTPRequestHandler):
    server_version = "GlimtServer/1.0"

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _headers(self, status=HTTPStatus.OK, content_type="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cache-Control", "no-store" if self.path.startswith("/api/") else "no-cache")
        self.end_headers()

    def _json(self, value, status=HTTPStatus.OK):
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self._headers(status)
        self.wfile.write(body)

    def do_GET(self):
        route = urlparse(self.path).path
        if route == "/api/health":
            return self._json({"ok": True, "service": "glimt"})
        if route == "/api/news":
            return self._json(read_json(NEWS_FILE, {"updatedAt": None, "articles": []}))
        if route == "/api/forum/topics":
            return self._json(visible_forum())
        self._serve_static(route)

    def do_POST(self):
        route = urlparse(self.path).path
        if route not in {"/api/forum/topics", "/api/forum/replies", "/api/newsletter"}:
            return self._json({"error": "Okänd endpoint"}, HTTPStatus.NOT_FOUND)

        size = int(self.headers.get("Content-Length", "0") or 0)
        if size <= 0 or size > MAX_BODY:
            return self._json({"error": "Ogiltig datamängd"}, HTTPStatus.BAD_REQUEST)
        try:
            payload = json.loads(self.rfile.read(size))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._json({"error": "Ogiltig JSON"}, HTTPStatus.BAD_REQUEST)

        if payload.get("website"):
            return self._json({"ok": True, "status": "pending"}, HTTPStatus.ACCEPTED)

        client = self.client_address[0]
        now = time.monotonic()
        with _rate_lock:
            if now - _last_post.get(client, 0) < RATE_LIMIT_SECONDS:
                return self._json(
                    {"error": "Vänta en liten stund innan du skickar igen."},
                    HTTPStatus.TOO_MANY_REQUESTS,
                )
            _last_post[client] = now

        if route == "/api/newsletter":
            email = clean_text(payload.get("email"), 180).lower()
            if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                return self._json({"error": "Kontrollera e-postadressen."}, HTTPStatus.BAD_REQUEST)
            return self._json({"ok": True, "message": "Tack! Du är anmäld till demolistan."})

        forum = read_json(FORUM_FILE, {"topics": []})
        timestamp = datetime.now(timezone.utc).isoformat()
        author = clean_text(payload.get("author"), 40) or "Anonym glädjespridare"
        body = clean_text(payload.get("body"), 1600)
        if len(body) < 10:
            return self._json({"error": "Skriv minst 10 tecken."}, HTTPStatus.BAD_REQUEST)

        if route == "/api/forum/topics":
            title = clean_text(payload.get("title"), 100)
            category = clean_text(payload.get("category"), 30) or "Samtal"
            if len(title) < 5:
                return self._json({"error": "Rubriken behöver minst 5 tecken."}, HTTPStatus.BAD_REQUEST)
            forum["topics"].insert(0, {
                "id": f"topic-{uuid.uuid4().hex[:10]}",
                "title": title,
                "category": category,
                "author": author,
                "body": body,
                "createdAt": timestamp,
                "status": "pending",
                "replies": [],
            })
        else:
            topic_id = clean_text(payload.get("topicId"), 80)
            topic = next((item for item in forum["topics"] if item.get("id") == topic_id), None)
            if not topic:
                return self._json({"error": "Tråden hittades inte."}, HTTPStatus.NOT_FOUND)
            topic.setdefault("replies", []).append({
                "id": f"reply-{uuid.uuid4().hex[:10]}",
                "author": author,
                "body": body,
                "createdAt": timestamp,
                "status": "pending",
            })

        atomic_write(FORUM_FILE, forum)
        self._json({
            "ok": True,
            "status": "pending",
            "message": "Tack! Inlägget väntar på en snabb modereringskontroll.",
        }, HTTPStatus.ACCEPTED)

    def _serve_static(self, route: str):
        route = unquote(route)
        aliases = {"/": "index.html", "/forum": "forum.html", "/om": "om.html"}
        relative = aliases.get(route, route.lstrip("/"))
        normalized = relative.replace("\\", "/")
        is_asset = normalized.startswith("assets/") and not any(
            part.startswith(".") for part in Path(normalized).parts
        )
        if normalized not in PUBLIC_PAGES and normalized not in PUBLIC_DATA and not is_asset:
            return self._json({"error": "Sidan hittades inte"}, HTTPStatus.NOT_FOUND)
        candidate = (ROOT / relative).resolve()
        if ROOT not in candidate.parents and candidate != ROOT:
            return self._json({"error": "Ogiltig sökväg"}, HTTPStatus.FORBIDDEN)
        if not candidate.is_file():
            candidate = ROOT / "404.html"
            if not candidate.is_file():
                return self._json({"error": "Sidan hittades inte"}, HTTPStatus.NOT_FOUND)
            status = HTTPStatus.NOT_FOUND
        else:
            status = HTTPStatus.OK
        mime = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        body = candidate.read_bytes()
        self._headers(status, f"{mime}; charset=utf-8" if mime.startswith("text/") else mime)
        self.wfile.write(body)


def main():
    host = os.getenv("GLIMT_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "4173"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Glimt Nyheter kör på http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServern stoppad.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
