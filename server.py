#!/usr/bin/env python3
"""Ljusglimt: webbserver, konton, profiler, sparade nyheter och modererat forum."""

from __future__ import annotations

import base64
from collections import OrderedDict
import hashlib
import ipaddress
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DIST_DIR = Path(os.getenv("GLIMT_DIST_PATH", str(ROOT / "dist")))
FORUM_SEED = DATA / "forum.json"
NEWS_FILE = DATA / "news.json"
DB_FILE = Path(os.getenv("GLIMT_DB_PATH", str(DATA / "glimt.db")))
PUBLIC_PAGES = {"index.html", "forum.html", "profil.html", "om.html", "404.html"}
PUBLIC_DATA = {"data/news.json", "data/seed-news.json"}
LEGACY_ALIASES = {
    "/": "index.html", "/index.html": "index.html",
    "/forum": "forum.html", "/forum/": "forum.html", "/forum.html": "forum.html",
    "/profil": "profil.html", "/profil/": "profil.html", "/profil.html": "profil.html",
    "/om": "om.html", "/om/": "om.html", "/om.html": "om.html",
}
MAX_BODY = 32_000
SESSION_DAYS = 30
FORUM_CATEGORIES = {"Vardagsglädje", "Lokalt", "Goda idéer", "Nyheter", "Miljö", "Vetenskap"}
FORUM_STRUCTURE = (
    {
        "id": "nyheter-framsteg", "title": "Nyheter & framsteg",
        "description": "Positiva händelser, forskning och lösningar som för världen framåt.",
        "sections": (
            ("dagens-nyheter", "Dagens positiva nyheter", "Diskutera dagens ljusaste nyheter och dela fler källor.", "☀"),
            ("miljo-klimat", "Miljö & klimat", "Naturvård, ren energi och lösningar för planeten.", "♻"),
            ("vetenskap-teknik", "Vetenskap & teknik", "Upptäckter och teknik som förbättrar människors liv.", "⚛"),
            ("halsa-liv", "Hälsa & livskvalitet", "Framsteg inom hälsa, omsorg och välmående.", "♥"),
        ),
    },
    {
        "id": "samhalle-vardag", "title": "Samhälle & vardag",
        "description": "Det goda som händer nära oss, i vardagen och kulturen.",
        "sections": (
            ("lokalt-engagemang", "Lokalt engagemang", "Initiativ, föreningar och eldsjälar där du bor.", "⌂"),
            ("vardagsgladje", "Vardagsglädje", "Små segrar, vänlighet och sådant som gjorde dagen bättre.", "☺"),
            ("kultur-kreativitet", "Kultur & kreativitet", "Musik, film, spel, konst och skapande som inspirerar.", "✦"),
        ),
    },
    {
        "id": "gemenskap", "title": "Gemenskap & Ljusglimt",
        "description": "Lär känna medlemmarna och hjälp gemenskapen att utvecklas.",
        "sections": (
            ("presentationer", "Presentationer", "Ny här? Säg hej och berätta lite om dig själv.", "👋"),
            ("goda-ideer", "Goda idéer", "Idéer, projekt och samarbeten som fler kan bygga vidare på.", "💡"),
            ("sajtsnack", "Om Ljusglimt", "Förslag, frågor, regler och återkoppling om sajten.", "⚙"),
        ),
    },
)
FORUM_CATEGORY_TO_SECTION = {
    "Vardagsglädje": "vardagsgladje", "Lokalt": "lokalt-engagemang",
    "Goda idéer": "goda-ideer", "Nyheter": "dagens-nyheter",
    "Miljö": "miljo-klimat", "Vetenskap": "vetenskap-teknik",
}
_rate_state: OrderedDict[tuple[str, str], float] = OrderedDict()
_rate_lock = threading.Lock()
RATE_STATE_MAX = 10_000
RATE_STATE_TTL = 3_600


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def clean_text(value, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def valid_email(value: str) -> bool:
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value)) and len(value) <= 180


def safe_http_url(value: str) -> str:
    value = clean_text(value, 1200)
    parsed = urlparse(value)
    return value if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def safe_saved_image(value: str) -> str:
    value = clean_text(value, 180)
    category_image = r"/news-images/ai/[a-z0-9-]+\.webp"
    article_image = r"/news-images/ai/articles/[a-f0-9]{20}-[a-f0-9]{8}-v1\.webp"
    return value if re.fullmatch(rf"(?:{category_image}|{article_image})", value) else ""


def read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


@contextmanager
def db_connect():
    connection = sqlite3.connect(DB_FILE, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def ensure_column(db: sqlite3.Connection, table: str, column: str, declaration: str) -> None:
    columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")


def init_db() -> None:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with db_connect() as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id TEXT PRIMARY KEY,
              email TEXT NOT NULL UNIQUE COLLATE NOCASE,
              name TEXT NOT NULL,
              password_hash TEXT,
              google_sub TEXT UNIQUE,
              avatar_url TEXT,
              role TEXT NOT NULL DEFAULT 'member',
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
              token_hash TEXT PRIMARY KEY,
              user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              expires_at TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS saved_articles (
              user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              article_id TEXT NOT NULL,
              title TEXT NOT NULL,
              summary TEXT NOT NULL DEFAULT '',
              source TEXT NOT NULL DEFAULT '',
              url TEXT NOT NULL,
              image TEXT NOT NULL DEFAULT '',
              saved_at TEXT NOT NULL,
              PRIMARY KEY (user_id, article_id)
            );
            CREATE TABLE IF NOT EXISTS forum_groups (
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              sort_order INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS forum_sections (
              id TEXT PRIMARY KEY,
              group_id TEXT NOT NULL REFERENCES forum_groups(id) ON DELETE CASCADE,
              title TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              icon TEXT NOT NULL DEFAULT '☀',
              sort_order INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS forum_topics (
              id TEXT PRIMARY KEY,
              user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
              author_name TEXT NOT NULL,
              title TEXT NOT NULL,
              category TEXT NOT NULL,
              body TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending',
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS forum_replies (
              id TEXT PRIMARY KEY,
              topic_id TEXT NOT NULL REFERENCES forum_topics(id) ON DELETE CASCADE,
              user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
              author_name TEXT NOT NULL,
              body TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending',
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS forum_reports (
              id TEXT PRIMARY KEY,
              topic_id TEXT NOT NULL REFERENCES forum_topics(id) ON DELETE CASCADE,
              user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              reason TEXT NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE(topic_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS forum_follows (
              user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              topic_id TEXT NOT NULL REFERENCES forum_topics(id) ON DELETE CASCADE,
              created_at TEXT NOT NULL,
              PRIMARY KEY (user_id, topic_id)
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
            CREATE INDEX IF NOT EXISTS idx_topics_status ON forum_topics(status, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_replies_topic ON forum_replies(topic_id, created_at);
            """
        )
        ensure_column(db, "forum_topics", "section_id", "TEXT")
        ensure_column(db, "forum_topics", "views", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(db, "forum_topics", "is_pinned", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(db, "forum_topics", "is_locked", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(db, "forum_topics", "last_activity", "TEXT")
        for group_order, group in enumerate(FORUM_STRUCTURE):
            db.execute(
                """INSERT INTO forum_groups(id,title,description,sort_order) VALUES (?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET title=excluded.title,description=excluded.description,sort_order=excluded.sort_order""",
                (group["id"], group["title"], group["description"], group_order),
            )
            for section_order, (section_id, title, description, icon) in enumerate(group["sections"]):
                db.execute(
                    """INSERT INTO forum_sections(id,group_id,title,description,icon,sort_order) VALUES (?,?,?,?,?,?)
                       ON CONFLICT(id) DO UPDATE SET group_id=excluded.group_id,title=excluded.title,
                       description=excluded.description,icon=excluded.icon,sort_order=excluded.sort_order""",
                    (section_id, group["id"], title, description, icon, section_order),
                )
        seed = read_json(FORUM_SEED, {"topics": []})
        for topic in seed.get("topics", []):
            replies = topic.get("replies", [])
            timestamps = [topic.get("createdAt", iso_now())] + [reply.get("createdAt", "") for reply in replies]
            last_activity = max(value for value in timestamps if value)
            db.execute(
                """INSERT OR IGNORE INTO forum_topics
                   (id,user_id,author_name,title,category,body,status,created_at,section_id,
                    views,is_pinned,is_locked,last_activity)
                   VALUES (?,NULL,?,?,?,?,?,?,?,?,?,?,?)""",
                (topic["id"], topic.get("author", "Redaktionen"), topic["title"],
                 topic.get("category", "Nyheter"), topic.get("body", ""),
                 topic.get("status", "published"), topic.get("createdAt", iso_now()),
                 topic.get("sectionId") or FORUM_CATEGORY_TO_SECTION.get(topic.get("category", "Nyheter"), "dagens-nyheter"),
                 int(topic.get("views", 0)), int(bool(topic.get("pinned"))), int(bool(topic.get("locked"))),
                 last_activity),
            )
            for reply in replies:
                db.execute(
                    """INSERT OR IGNORE INTO forum_replies
                       (id,topic_id,user_id,author_name,body,status,created_at) VALUES (?,?,NULL,?,?,?,?)""",
                    (reply["id"], topic["id"], reply.get("author", "Redaktionen"),
                     reply.get("body", ""), reply.get("status", "published"),
                     reply.get("createdAt", iso_now())),
                )
        for category, section_id in FORUM_CATEGORY_TO_SECTION.items():
            db.execute(
                "UPDATE forum_topics SET section_id=? WHERE (section_id IS NULL OR section_id='') AND category=?",
                (section_id, category),
            )
        db.execute("UPDATE forum_topics SET section_id='dagens-nyheter' WHERE section_id IS NULL OR section_id=''")
        db.execute("UPDATE forum_topics SET last_activity=created_at WHERE last_activity IS NULL OR last_activity=''")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(digest).decode()


def verify_password(password: str, encoded: str | None) -> bool:
    try:
        algorithm, salt_text, digest_text = (encoded or "").split("$", 2)
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_text)
        expected = base64.urlsafe_b64decode(digest_text)
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return secrets.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def user_public(row: sqlite3.Row | dict) -> dict:
    return {
        "id": row["id"], "email": row["email"], "name": row["name"],
        "avatarUrl": row["avatar_url"], "role": row["role"],
    }


def create_session(user_id: str) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    expires = utc_now() + timedelta(days=SESSION_DAYS)
    with db_connect() as db:
        db.execute("DELETE FROM sessions WHERE expires_at <= ?", (iso_now(),))
        db.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?)",
            (token_hash(token), user_id, expires.isoformat(), iso_now()),
        )
        db.execute(
            """DELETE FROM sessions WHERE user_id=? AND token_hash NOT IN
               (SELECT token_hash FROM sessions WHERE user_id=? ORDER BY created_at DESC LIMIT 10)""",
            (user_id, user_id),
        )
    return token, expires


def validate_google_profile(profile: dict, client_id: str) -> dict:
    verified = profile.get("email_verified")
    if profile.get("aud") != client_id or verified not in {"true", True}:
        raise ValueError("Google-kontot kunde inte verifieras.")
    try:
        expires = int(profile.get("exp", "0"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Google-inloggningen saknar giltig livslängd.") from exc
    if expires <= int(time.time()):
        raise ValueError("Google-inloggningen har gått ut.")
    if not profile.get("sub") or not valid_email(str(profile.get("email") or "")):
        raise ValueError("Google-kontot saknar nödvändiga identitetsuppgifter.")
    return profile


def google_identity(credential: str) -> dict:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        raise ValueError("Google-inloggning är inte aktiverad ännu.")
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token
        profile = google_id_token.verify_oauth2_token(credential, google_requests.Request(), client_id)
    except ImportError:
        query = urllib.parse.urlencode({"id_token": credential})
        request = urllib.request.Request(
            f"https://oauth2.googleapis.com/tokeninfo?{query}",
            headers={"User-Agent": "Ljusglimt/1.0"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            profile = json.loads(response.read().decode("utf-8"))
    return validate_google_profile(profile, client_id)


def forum_index_payload(current_user: dict | None = None) -> dict:
    with db_connect() as db:
        groups = []
        for group in db.execute("SELECT * FROM forum_groups ORDER BY sort_order,title").fetchall():
            sections = []
            rows = db.execute(
                "SELECT * FROM forum_sections WHERE group_id=? ORDER BY sort_order,title", (group["id"],)
            ).fetchall()
            for section in rows:
                topic_count = db.execute(
                    "SELECT COUNT(*) FROM forum_topics WHERE section_id=? AND status='published'", (section["id"],)
                ).fetchone()[0]
                reply_count = db.execute(
                    """SELECT COUNT(*) FROM forum_replies r JOIN forum_topics t ON t.id=r.topic_id
                       WHERE t.section_id=? AND t.status='published' AND r.status='published'""", (section["id"],)
                ).fetchone()[0]
                latest = db.execute(
                    """SELECT id,title,author_name,last_activity FROM forum_topics
                       WHERE section_id=? AND status='published'
                       ORDER BY last_activity DESC LIMIT 1""", (section["id"],)
                ).fetchone()
                sections.append({
                    "id": section["id"], "title": section["title"],
                    "description": section["description"], "icon": section["icon"],
                    "topicCount": topic_count, "postCount": topic_count + reply_count,
                    "latest": ({"id": latest["id"], "title": latest["title"],
                                "author": latest["author_name"], "createdAt": latest["last_activity"]}
                               if latest else None),
                })
            groups.append({
                "id": group["id"], "title": group["title"],
                "description": group["description"], "sections": sections,
            })
        latest_rows = db.execute(
            """SELECT t.id,t.title,t.author_name,t.last_activity,t.section_id,s.title AS section_title
               FROM forum_topics t JOIN forum_sections s ON s.id=t.section_id
               WHERE t.status='published' ORDER BY t.last_activity DESC LIMIT 8"""
        ).fetchall()
        stats = {
            "topics": db.execute("SELECT COUNT(*) FROM forum_topics WHERE status='published'").fetchone()[0],
            "posts": db.execute("SELECT COUNT(*) FROM forum_topics WHERE status='published'").fetchone()[0]
                     + db.execute("SELECT COUNT(*) FROM forum_replies WHERE status='published'").fetchone()[0],
            "members": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        }
    return {
        "groups": groups,
        "latest": [{"id": row["id"], "title": row["title"], "author": row["author_name"],
                    "createdAt": row["last_activity"], "sectionId": row["section_id"],
                    "sectionTitle": row["section_title"]} for row in latest_rows],
        "stats": stats,
    }


def forum_topics_payload(section_id: str, current_user: dict | None) -> dict | None:
    user_id = current_user["id"] if current_user else ""
    with db_connect() as db:
        section = db.execute(
            """SELECT s.*,g.title AS group_title,g.id AS group_id
               FROM forum_sections s JOIN forum_groups g ON g.id=s.group_id WHERE s.id=?""", (section_id,)
        ).fetchone()
        if not section:
            return None
        topics = db.execute(
            """SELECT t.*,u.avatar_url,
                      (SELECT COUNT(*) FROM forum_replies r WHERE r.topic_id=t.id AND r.status='published') AS reply_count,
                      EXISTS(SELECT 1 FROM forum_follows f WHERE f.topic_id=t.id AND f.user_id=?) AS followed
               FROM forum_topics t LEFT JOIN users u ON u.id=t.user_id
               WHERE t.section_id=? AND (t.status='published' OR t.user_id=?)
               ORDER BY t.is_pinned DESC,t.last_activity DESC""", (user_id, section_id, user_id)
        ).fetchall()
    return {
        "section": {"id": section["id"], "title": section["title"],
                    "description": section["description"], "icon": section["icon"],
                    "groupId": section["group_id"], "groupTitle": section["group_title"]},
        "topics": [{
            "id": row["id"], "title": row["title"], "body": row["body"],
            "author": row["author_name"], "avatarUrl": row["avatar_url"],
            "createdAt": row["created_at"], "lastActivity": row["last_activity"],
            "status": row["status"], "replyCount": row["reply_count"], "views": row["views"],
            "pinned": bool(row["is_pinned"]), "locked": bool(row["is_locked"]),
            "followed": bool(row["followed"]),
        } for row in topics],
    }


def forum_topic_payload(topic_id: str, current_user: dict | None, increment_view: bool = True) -> dict | None:
    user_id = current_user["id"] if current_user else ""
    with db_connect() as db:
        visible = db.execute(
            "SELECT id,status FROM forum_topics WHERE id=? AND (status='published' OR user_id=?)",
            (topic_id, user_id),
        ).fetchone()
        if not visible:
            return None
        if increment_view and visible["status"] == "published":
            db.execute("UPDATE forum_topics SET views=views+1 WHERE id=?", (topic_id,))
        topic = db.execute(
            """SELECT t.*,u.avatar_url,u.created_at AS member_since,u.role,
                      s.title AS section_title,s.description AS section_description,s.icon AS section_icon,
                      g.id AS group_id,g.title AS group_title,
                      EXISTS(SELECT 1 FROM forum_follows f WHERE f.topic_id=t.id AND f.user_id=?) AS followed
               FROM forum_topics t LEFT JOIN users u ON u.id=t.user_id
               JOIN forum_sections s ON s.id=t.section_id JOIN forum_groups g ON g.id=s.group_id
               WHERE t.id=?""", (user_id, topic_id)
        ).fetchone()
        replies = db.execute(
            """SELECT r.*,u.avatar_url,u.created_at AS member_since,u.role
               FROM forum_replies r LEFT JOIN users u ON u.id=r.user_id
               WHERE r.topic_id=? AND (r.status='published' OR r.user_id=?) ORDER BY r.created_at""",
            (topic_id, user_id),
        ).fetchall()
    author = {
        "name": topic["author_name"], "avatarUrl": topic["avatar_url"],
        "memberSince": topic["member_since"], "role": topic["role"] or "member",
    }
    return {
        "section": {"id": topic["section_id"], "title": topic["section_title"],
                    "description": topic["section_description"], "icon": topic["section_icon"],
                    "groupId": topic["group_id"], "groupTitle": topic["group_title"]},
        "topic": {
            "id": topic["id"], "title": topic["title"], "body": topic["body"],
            "author": author, "createdAt": topic["created_at"], "lastActivity": topic["last_activity"],
            "status": topic["status"], "views": topic["views"], "pinned": bool(topic["is_pinned"]),
            "locked": bool(topic["is_locked"]), "followed": bool(topic["followed"]),
            "replies": [{
                "id": row["id"], "body": row["body"], "createdAt": row["created_at"],
                "status": row["status"], "author": {"name": row["author_name"],
                "avatarUrl": row["avatar_url"], "memberSince": row["member_since"],
                "role": row["role"] or "member"},
            } for row in replies],
        },
    }


def forum_payload(current_user: dict | None) -> dict:
    """Bakåtkompatibel lista för äldre klienter och tester."""
    user_id = current_user["id"] if current_user else ""
    with db_connect() as db:
        topics = db.execute(
            """SELECT t.* FROM forum_topics t WHERE t.status='published' OR t.user_id=?
               ORDER BY t.last_activity DESC""", (user_id,)
        ).fetchall()
    return {"topics": [dict(row) for row in topics], "categories": sorted(FORUM_CATEGORIES)}


class Handler(BaseHTTPRequestHandler):
    server_version = "Ljusglimt/3.0"

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _headers(self, status=HTTPStatus.OK, content_type="application/json; charset=utf-8", extra=None):
        extra = dict(extra or {})
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin-allow-popups")
        self.send_header("Content-Security-Policy", "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; script-src 'self' https://accounts.google.com; style-src 'self' 'unsafe-inline' https://accounts.google.com; frame-src https://accounts.google.com; connect-src 'self' https://accounts.google.com https://oauth2.googleapis.com; img-src 'self' data: https:")
        self.send_header("Cache-Control", extra.pop(
            "Cache-Control", "no-store" if self.path.startswith("/api/") else "no-cache"
        ))
        for key, value in extra.items():
            self.send_header(key, value)
        self.end_headers()

    def _json(self, value, status=HTTPStatus.OK, extra=None):
        self._headers(status, extra=extra)
        self.wfile.write(json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def _payload(self) -> dict | None:
        try:
            size = int(self.headers.get("Content-Length", "0") or 0)
            if size <= 0 or size > MAX_BODY:
                return None
            value = json.loads(self.rfile.read(size))
            return value if isinstance(value, dict) else None
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            return None

    def _same_origin(self) -> bool:
        origin = self.headers.get("Origin")
        return not origin or urlparse(origin).netloc == self.headers.get("Host", "")

    def _rate_ok(self, bucket: str, seconds: int) -> bool:
        client_ip = self.client_address[0]
        if os.getenv("GLIMT_TRUST_PROXY", "").strip().lower() in {"1", "true", "yes"}:
            forwarded = self.headers.get("CF-Connecting-IP", "").strip()
            try:
                client_ip = str(ipaddress.ip_address(forwarded))
            except ValueError:
                pass
        key = (client_ip, bucket)
        now = time.monotonic()
        with _rate_lock:
            while _rate_state:
                oldest_key, oldest = next(iter(_rate_state.items()))
                if now - oldest <= RATE_STATE_TTL:
                    break
                _rate_state.pop(oldest_key, None)
            if now - _rate_state.get(key, 0) < seconds:
                return False
            _rate_state[key] = now
            _rate_state.move_to_end(key)
            while len(_rate_state) > RATE_STATE_MAX:
                _rate_state.popitem(last=False)
        return True

    def _current_user(self) -> dict | None:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get("glimt_session")
        if not morsel:
            return None
        with db_connect() as db:
            row = db.execute(
                """SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id
                   WHERE s.token_hash=? AND s.expires_at>?""",
                (token_hash(morsel.value), iso_now()),
            ).fetchone()
        return user_public(row) if row else None

    def _require_user(self) -> dict | None:
        user = self._current_user()
        if not user:
            self._json({"error": "Logga in för att fortsätta.", "code": "AUTH_REQUIRED"}, HTTPStatus.UNAUTHORIZED)
        return user

    def _secure_cookie_enabled(self) -> bool:
        secure_setting = os.getenv("GLIMT_SECURE_COOKIES", "").strip().lower() in {"1", "true", "yes"}
        trusted_https = (os.getenv("GLIMT_TRUST_PROXY", "").strip().lower() in {"1", "true", "yes"}
                         and self.headers.get("X-Forwarded-Proto") == "https")
        return secure_setting or trusted_https

    def _session_cookie(self, token: str, expires: datetime) -> str:
        value = f"glimt_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_DAYS * 86400}; Expires={format_datetime(expires, usegmt=True)}"
        return value + ("; Secure" if self._secure_cookie_enabled() else "")

    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        if route == "/api/health":
            return self._json({"ok": True, "service": "ljusglimt", "version": 3})
        if route == "/api/config":
            client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
            return self._json({"googleClientId": client_id, "googleEnabled": bool(client_id)})
        if route == "/api/news":
            try:
                return self._json(json.loads(NEWS_FILE.read_text(encoding="utf-8")))
            except FileNotFoundError:
                return self._json({"items": []})
            except json.JSONDecodeError:
                return self._json({"error": "Nyhetsdatan är tillfälligt otillgänglig."}, HTTPStatus.SERVICE_UNAVAILABLE)
        if route == "/api/auth/me":
            user = self._current_user()
            return self._json({"user": user})
        if route == "/api/saved":
            user = self._require_user()
            if not user:
                return
            with db_connect() as db:
                rows = db.execute(
                    "SELECT * FROM saved_articles WHERE user_id=? ORDER BY saved_at DESC", (user["id"],)
                ).fetchall()
            return self._json({"articles": [dict(row) for row in rows]})
        if route == "/api/forum/index" or route == "/api/forum/latest":
            return self._json(forum_index_payload(self._current_user()))
        if route == "/api/forum/topics":
            section_id = clean_text((query.get("section") or [""])[0], 80)
            if not section_id:
                return self._json(forum_payload(self._current_user()))
            result = forum_topics_payload(section_id, self._current_user())
            return self._json(result, HTTPStatus.OK) if result else self._json({"error": "Forumdelen hittades inte."}, HTTPStatus.NOT_FOUND)
        if route == "/api/forum/topic":
            topic_id = clean_text((query.get("id") or [""])[0], 80)
            result = forum_topic_payload(topic_id, self._current_user(), self._rate_ok(f"view:{topic_id}", 300))
            return self._json(result, HTTPStatus.OK) if result else self._json({"error": "Tråden hittades inte."}, HTTPStatus.NOT_FOUND)
        if route == "/api" or route.startswith("/api/"):
            return self._json({"error": "Okänd endpoint."}, HTTPStatus.NOT_FOUND)
        self._serve_static(route)

    def do_POST(self):
        route = urlparse(self.path).path
        if not self._same_origin():
            return self._json({"error": "Begäran blockerades."}, HTTPStatus.FORBIDDEN)
        payload = self._payload()
        if payload is None:
            return self._json({"error": "Ogiltig datamängd."}, HTTPStatus.BAD_REQUEST)
        if payload.get("website"):
            return self._json({"ok": True}, HTTPStatus.ACCEPTED)

        if route == "/api/auth/register":
            return self._register(payload)
        if route == "/api/auth/login":
            return self._login(payload)
        if route == "/api/auth/google":
            return self._google_login(payload)
        if route == "/api/auth/logout":
            return self._logout()
        if route == "/api/profile":
            return self._update_profile(payload)
        if route == "/api/saved":
            return self._save_article(payload)
        if route == "/api/forum/topics":
            return self._create_topic(payload)
        if route == "/api/forum/replies":
            return self._create_reply(payload)
        if route == "/api/forum/report":
            return self._report_topic(payload)
        if route == "/api/forum/follow":
            return self._follow_topic(payload)
        if route == "/api/newsletter":
            email = clean_text(payload.get("email"), 180).lower()
            if not valid_email(email):
                return self._json({"error": "Kontrollera e-postadressen."}, HTTPStatus.BAD_REQUEST)
            return self._json({"ok": True, "message": "Adressen kontrollerades men sparades inte ännu."})
        self._json({"error": "Okänd endpoint."}, HTTPStatus.NOT_FOUND)

    def do_DELETE(self):
        route = urlparse(self.path).path
        if not self._same_origin():
            return self._json({"error": "Begäran blockerades."}, HTTPStatus.FORBIDDEN)
        if route.startswith("/api/saved/"):
            user = self._require_user()
            if not user:
                return
            article_id = clean_text(unquote(route.removeprefix("/api/saved/")), 140)
            with db_connect() as db:
                db.execute("DELETE FROM saved_articles WHERE user_id=? AND article_id=?", (user["id"], article_id))
            return self._json({"ok": True})
        if route.startswith("/api/forum/follow/"):
            user = self._require_user()
            if not user:
                return
            topic_id = clean_text(unquote(route.removeprefix("/api/forum/follow/")), 80)
            with db_connect() as db:
                db.execute("DELETE FROM forum_follows WHERE user_id=? AND topic_id=?", (user["id"], topic_id))
            return self._json({"ok": True, "followed": False})
        self._json({"error": "Okänd endpoint."}, HTTPStatus.NOT_FOUND)

    def _register(self, payload: dict):
        if not self._rate_ok("register", 3):
            return self._json({"error": "Vänta några sekunder och försök igen."}, HTTPStatus.TOO_MANY_REQUESTS)
        name = clean_text(payload.get("name"), 50)
        email = clean_text(payload.get("email"), 180).lower()
        password = str(payload.get("password") or "")
        if len(password) > 256:
            return self._json({"error": "Fel e-post eller lösenord."}, HTTPStatus.UNAUTHORIZED)
        if len(name) < 2 or not valid_email(email) or not 8 <= len(password) <= 256:
            return self._json({"error": "Ange namn, giltig e-post och 8–256 tecken i lösenordet."}, HTTPStatus.BAD_REQUEST)
        user_id = f"user-{secrets.token_hex(8)}"
        try:
            with db_connect() as db:
                db.execute(
                    "INSERT INTO users(id,email,name,password_hash,created_at) VALUES (?,?,?,?,?)",
                    (user_id, email, name, hash_password(password), iso_now()),
                )
        except sqlite3.IntegrityError:
            return self._json({"error": "Det finns redan ett konto med den e-postadressen."}, HTTPStatus.CONFLICT)
        token, expires = create_session(user_id)
        with db_connect() as db:
            user = user_public(db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
        self._json({"ok": True, "user": user}, HTTPStatus.CREATED, {"Set-Cookie": self._session_cookie(token, expires)})

    def _login(self, payload: dict):
        if not self._rate_ok("login", 2):
            return self._json({"error": "Vänta ett ögonblick och försök igen."}, HTTPStatus.TOO_MANY_REQUESTS)
        email = clean_text(payload.get("email"), 180).lower()
        password = str(payload.get("password") or "")
        with db_connect() as db:
            row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            return self._json({"error": "Fel e-post eller lösenord."}, HTTPStatus.UNAUTHORIZED)
        token, expires = create_session(row["id"])
        self._json({"ok": True, "user": user_public(row)}, extra={"Set-Cookie": self._session_cookie(token, expires)})

    def _google_login(self, payload: dict):
        if not self._rate_ok("google", 2):
            return self._json({"error": "Vänta ett ögonblick och försök igen."}, HTTPStatus.TOO_MANY_REQUESTS)
        try:
            profile = google_identity(clean_text(payload.get("credential"), 5000))
        except Exception as exc:
            self.log_error("Google login failed: %s", clean_text(exc, 180))
            return self._json({"error": "Google-kontot kunde inte verifieras."}, HTTPStatus.UNAUTHORIZED)
        email = profile["email"].lower()
        with db_connect() as db:
            row = db.execute("SELECT * FROM users WHERE google_sub=?", (profile["sub"],)).fetchone()
            if row:
                db.execute(
                    "UPDATE users SET avatar_url=COALESCE(?,avatar_url) WHERE id=?",
                    (safe_http_url(profile.get("picture", "")) or None, row["id"]),
                )
                user_id = row["id"]
            else:
                existing_email = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
                if existing_email:
                    return self._json({"error": "E-postadressen har redan ett konto. Logga in med lösenord först."}, HTTPStatus.CONFLICT)
                user_id = f"user-{secrets.token_hex(8)}"
                try:
                    db.execute(
                        "INSERT INTO users(id,email,name,google_sub,avatar_url,created_at) VALUES (?,?,?,?,?,?)",
                        (user_id, email, clean_text(profile.get("name"), 50) or email.split("@")[0],
                         profile["sub"], safe_http_url(profile.get("picture", "")), iso_now()),
                    )
                except sqlite3.IntegrityError:
                    return self._json({"error": "Google-kontot kunde inte kopplas just nu."}, HTTPStatus.CONFLICT)
            row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        token, expires = create_session(user_id)
        self._json({"ok": True, "user": user_public(row)}, extra={"Set-Cookie": self._session_cookie(token, expires)})

    def _logout(self):
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get("glimt_session")
        if morsel:
            with db_connect() as db:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(morsel.value),))
        expired = "glimt_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"
        self._json({"ok": True}, extra={"Set-Cookie": expired + ("; Secure" if self._secure_cookie_enabled() else "")})

    def _update_profile(self, payload: dict):
        user = self._require_user()
        if not user:
            return
        name = clean_text(payload.get("name"), 50)
        if len(name) < 2:
            return self._json({"error": "Namnet behöver minst två tecken."}, HTTPStatus.BAD_REQUEST)
        with db_connect() as db:
            db.execute("UPDATE users SET name=? WHERE id=?", (name, user["id"]))
            row = db.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
        self._json({"ok": True, "user": user_public(row)})

    def _save_article(self, payload: dict):
        user = self._require_user()
        if not user:
            return
        article_id = clean_text(payload.get("id"), 140)
        title = clean_text(payload.get("title"), 260)
        url = safe_http_url(payload.get("url", ""))
        if not article_id or not title or not url:
            return self._json({"error": "Nyheten saknar nödvändiga fält."}, HTTPStatus.BAD_REQUEST)
        with db_connect() as db:
            db.execute(
                """INSERT INTO saved_articles(user_id,article_id,title,summary,source,url,image,saved_at)
                   VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(user_id,article_id) DO UPDATE SET
                   title=excluded.title,summary=excluded.summary,source=excluded.source,
                   url=excluded.url,image=excluded.image,saved_at=excluded.saved_at""",
                (user["id"], article_id, title, clean_text(payload.get("excerpt"), 1400),
                 clean_text(payload.get("source"), 120), url, safe_saved_image(payload.get("image", "")), iso_now()),
            )
        self._json({"ok": True, "saved": True}, HTTPStatus.CREATED)

    def _create_topic(self, payload: dict):
        user = self._require_user()
        if not user:
            return
        if not self._rate_ok("topic", 20):
            return self._json({"error": "Vänta en liten stund innan du postar igen."}, HTTPStatus.TOO_MANY_REQUESTS)
        title = clean_text(payload.get("title"), 100)
        body = clean_text(payload.get("body"), 2000)
        category = clean_text(payload.get("category"), 30)
        section_id = clean_text(payload.get("sectionId"), 80) or FORUM_CATEGORY_TO_SECTION.get(category, "")
        if len(title) < 5 or len(body) < 10:
            return self._json({"error": "Kontrollera rubrik och innehåll."}, HTTPStatus.BAD_REQUEST)
        topic_id = f"topic-{secrets.token_hex(6)}"
        created_at = iso_now()
        with db_connect() as db:
            section = db.execute("SELECT title FROM forum_sections WHERE id=?", (section_id,)).fetchone()
            if not section:
                return self._json({"error": "Välj ett giltigt underforum."}, HTTPStatus.BAD_REQUEST)
            db.execute(
                """INSERT INTO forum_topics
                   (id,user_id,author_name,title,category,body,status,created_at,section_id,last_activity)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (topic_id, user["id"], user["name"], title, category or section["title"], body,
                 "pending", created_at, section_id, created_at),
            )
        self._json({"ok": True, "topicId": topic_id, "status": "pending",
                    "message": "Tråden är sparad och väntar på moderering."}, HTTPStatus.ACCEPTED)

    def _create_reply(self, payload: dict):
        user = self._require_user()
        if not user:
            return
        if not self._rate_ok("reply", 10):
            return self._json({"error": "Vänta en liten stund innan du svarar igen."}, HTTPStatus.TOO_MANY_REQUESTS)
        topic_id = clean_text(payload.get("topicId"), 80)
        body = clean_text(payload.get("body"), 1600)
        if len(body) < 10:
            return self._json({"error": "Svaret behöver minst 10 tecken."}, HTTPStatus.BAD_REQUEST)
        with db_connect() as db:
            topic = db.execute(
                "SELECT id,is_locked FROM forum_topics WHERE id=? AND status='published'", (topic_id,)
            ).fetchone()
            if not topic:
                return self._json({"error": "Tråden hittades inte."}, HTTPStatus.NOT_FOUND)
            if topic["is_locked"]:
                return self._json({"error": "Tråden är låst för nya svar."}, HTTPStatus.CONFLICT)
            db.execute(
                """INSERT INTO forum_replies(id,topic_id,user_id,author_name,body,status,created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (f"reply-{secrets.token_hex(6)}", topic_id, user["id"], user["name"], body, "pending", iso_now()),
            )
        self._json({"ok": True, "status": "pending", "message": "Svaret väntar på moderering."}, HTTPStatus.ACCEPTED)

    def _report_topic(self, payload: dict):
        user = self._require_user()
        if not user:
            return
        topic_id = clean_text(payload.get("topicId"), 80)
        reason = clean_text(payload.get("reason"), 300) or "Olämpligt innehåll"
        try:
            with db_connect() as db:
                db.execute(
                    "INSERT INTO forum_reports VALUES (?,?,?,?,?)",
                    (f"report-{secrets.token_hex(6)}", topic_id, user["id"], reason, iso_now()),
                )
        except sqlite3.IntegrityError:
            return self._json({"error": "Du har redan rapporterat den tråden."}, HTTPStatus.CONFLICT)
        self._json({"ok": True, "message": "Tack. Moderatorerna granskar tråden."}, HTTPStatus.CREATED)

    def _follow_topic(self, payload: dict):
        user = self._require_user()
        if not user:
            return
        topic_id = clean_text(payload.get("topicId"), 80)
        with db_connect() as db:
            topic = db.execute("SELECT id FROM forum_topics WHERE id=? AND status='published'", (topic_id,)).fetchone()
            if not topic:
                return self._json({"error": "Tråden hittades inte."}, HTTPStatus.NOT_FOUND)
            db.execute(
                "INSERT OR IGNORE INTO forum_follows(user_id,topic_id,created_at) VALUES (?,?,?)",
                (user["id"], topic_id, iso_now()),
            )
        self._json({"ok": True, "followed": True, "message": "Du följer nu tråden."}, HTTPStatus.CREATED)

    def _serve_static(self, route: str):
        try:
            decoded = unquote(route, errors="strict")
        except UnicodeDecodeError:
            return self._json({"error": "Ogiltig sökväg"}, HTTPStatus.BAD_REQUEST)
        if not decoded.startswith("/") or "\\" in decoded or "\x00" in decoded:
            return self._json({"error": "Ogiltig sökväg"}, HTTPStatus.FORBIDDEN)

        relative = decoded.lstrip("/")
        parts = tuple(part for part in relative.split("/") if part)
        if any(part in {".", ".."} or part.startswith(".") for part in parts):
            return self._json({"error": "Ogiltig sökväg"}, HTTPStatus.FORBIDDEN)

        normalized = "/".join(parts)
        if normalized in PUBLIC_DATA:
            candidate = self._safe_static_candidate(ROOT, normalized)
            return self._send_static_file(candidate) if candidate and candidate.is_file() else self._static_not_found()

        # A built Vite app is authoritative when dist/index.html exists.
        dist_index = self._safe_static_candidate(DIST_DIR, "index.html")
        if dist_index and dist_index.is_file():
            if decoded in LEGACY_ALIASES:
                return self._send_static_file(dist_index)
            candidate = self._safe_static_candidate(DIST_DIR, normalized)
            if candidate and candidate.is_file():
                cache = ("public, max-age=31536000, immutable" if normalized.startswith("assets/")
                         else "public, max-age=604800" if normalized.startswith("news-images/")
                         else "no-cache")
                return self._send_static_file(candidate, cache_control=cache)
            # Missing file-like requests must not receive HTML with status 200.
            if Path(normalized).suffix:
                return self._static_not_found()
            return self._send_static_file(dist_index)

        # Development fallback keeps the previous dependency-free site usable.
        legacy_relative = LEGACY_ALIASES.get(decoded, normalized)
        is_asset = legacy_relative.startswith("assets/")
        if legacy_relative not in PUBLIC_PAGES and not is_asset:
            return self._static_not_found()
        candidate = self._safe_static_candidate(ROOT, legacy_relative)
        return self._send_static_file(candidate) if candidate and candidate.is_file() else self._static_not_found()

    @staticmethod
    def _safe_static_candidate(base: Path, relative: str) -> Path | None:
        base = base.resolve()
        candidate = (base / relative).resolve()
        return candidate if candidate == base or base in candidate.parents else None

    def _send_static_file(self, candidate: Path, status=HTTPStatus.OK, cache_control="no-cache"):
        content = candidate.read_bytes()
        mime = {".webp": "image/webp", ".avif": "image/avif"}.get(candidate.suffix.casefold())
        mime = mime or mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        content_type = f"{mime}; charset=utf-8" if mime.startswith("text/") or mime in {"application/javascript", "application/json"} else mime
        self._headers(status, content_type, {
            "Cache-Control": cache_control,
            "Content-Length": str(len(content)),
        })
        self.wfile.write(content)

    def _static_not_found(self):
        not_found = self._safe_static_candidate(DIST_DIR, "404.html")
        if not not_found or not not_found.is_file():
            not_found = self._safe_static_candidate(ROOT, "404.html")
        if not_found and not_found.is_file():
            return self._send_static_file(not_found, HTTPStatus.NOT_FOUND)
        return self._json({"error": "Sidan hittades inte"}, HTTPStatus.NOT_FOUND)


def main():
    init_db()
    host = os.getenv("GLIMT_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "4173"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Ljusglimt kör på http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServern stoppad.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
