import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ModerateForumTests(unittest.TestCase):
    def test_approving_a_reply_updates_topic_activity(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "forum.db"
            db = sqlite3.connect(database)
            try:
                db.execute("CREATE TABLE forum_topics(id TEXT PRIMARY KEY,status TEXT,last_activity TEXT)")
                db.execute("CREATE TABLE forum_replies(id TEXT PRIMARY KEY,topic_id TEXT,status TEXT,created_at TEXT)")
                db.execute("INSERT INTO forum_topics VALUES ('topic-1','published','2026-01-01T00:00:00+00:00')")
                db.execute("INSERT INTO forum_replies VALUES ('reply-1','topic-1','pending','2026-07-15T01:00:00+00:00')")
                db.commit()
            finally:
                db.close()
            env = {**os.environ, "GLIMT_DB_PATH": str(database)}
            script = Path(__file__).resolve().parents[1] / "scripts/moderate_forum.py"
            result = subprocess.run(
                [sys.executable, str(script), "--approve", "reply-1"],
                env=env, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            db = sqlite3.connect(database)
            try:
                status = db.execute("SELECT status FROM forum_replies WHERE id='reply-1'").fetchone()[0]
                activity = db.execute("SELECT last_activity FROM forum_topics WHERE id='topic-1'").fetchone()[0]
            finally:
                db.close()
            self.assertEqual(status, "published")
            self.assertEqual(activity, "2026-07-15T01:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
