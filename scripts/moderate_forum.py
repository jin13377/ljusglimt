#!/usr/bin/env python3
"""Lista, godkänn eller avslå väntande forumtrådar och svar i SQLite."""

import argparse
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = Path(os.getenv("GLIMT_DB_PATH", str(ROOT / "data" / "glimt.db")))


def main():
    parser = argparse.ArgumentParser()
    decision = parser.add_mutually_exclusive_group()
    decision.add_argument("--approve", help="ID för tråd eller svar")
    decision.add_argument("--reject", help="ID för tråd eller svar")
    args = parser.parse_args()
    if not DB.exists():
        raise SystemExit("Databasen finns inte. Starta server.py först.")
    with sqlite3.connect(DB) as db:
        if not (args.approve or args.reject):
            for table in ("forum_topics", "forum_replies"):
                rows = db.execute(f"SELECT id,author_name,COALESCE(title,body) FROM {table} WHERE status='pending'" if table == "forum_topics" else "SELECT id,author_name,body FROM forum_replies WHERE status='pending'").fetchall()
                for item_id, author, text in rows:
                    print(f"{item_id} | {author} | {text[:90]}")
            return
        item_id = args.approve or args.reject
        status = "published" if args.approve else "rejected"
        changed = 0
        for table in ("forum_topics", "forum_replies"):
            reply = None
            if table == "forum_replies" and status == "published":
                reply = db.execute(
                    "SELECT topic_id,created_at FROM forum_replies WHERE id=? AND status='pending'", (item_id,)
                ).fetchone()
            cursor = db.execute(f"UPDATE {table} SET status=? WHERE id=? AND status='pending'", (status, item_id))
            changed += cursor.rowcount
            if reply and cursor.rowcount:
                db.execute(
                    """UPDATE forum_topics SET last_activity=CASE
                       WHEN last_activity IS NULL OR last_activity < ? THEN ? ELSE last_activity END
                       WHERE id=?""",
                    (reply[1], reply[1], reply[0]),
                )
        if not changed:
            raise SystemExit("ID hittades inte bland väntande inlägg.")
    print(f"{item_id} markerades som {status}.")


if __name__ == "__main__":
    main()
