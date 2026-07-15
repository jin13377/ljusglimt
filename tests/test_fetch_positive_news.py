import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/fetch_positive_news.py"
SPEC = importlib.util.spec_from_file_location("fetch_positive_news", MODULE_PATH)
news = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(news)


class PositiveNewsTests(unittest.TestCase):
    def test_schedule_runs_at_midnight_and_noon_stockholm(self):
        winter_midnight = datetime(2026, 1, 14, 23, 10, tzinfo=timezone.utc)
        summer_noon = datetime(2026, 7, 15, 10, 10, tzinfo=timezone.utc)
        outside_schedule = datetime(2026, 7, 15, 11, 10, tzinfo=timezone.utc)
        self.assertTrue(news.should_run(False, winter_midnight))
        self.assertTrue(news.should_run(False, summer_noon))
        self.assertFalse(news.should_run(False, outside_schedule))
        self.assertEqual(news.publication_slot(winter_midnight), "2026-01-15T00:00")
        self.assertEqual(news.publication_slot(summer_noon), "2026-07-15T12:00")

    def test_rss_parse_and_tracking_cleanup(self):
        xml = b"""<rss><channel><item><title>Community rescue success</title>
        <link>https://example.com/story?utm_source=x&amp;keep=1</link>
        <description>Volunteers helped.</description>
        <pubDate>Mon, 14 Jul 2025 08:00:00 GMT</pubDate></item></channel></rss>"""
        items = news.parse_feed(xml, "Example", "en")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["url"], "https://example.com/story?keep=1")
        self.assertEqual(items[0]["source"], "Example")

    def test_blocked_topic_is_rejected(self):
        item = {"title": "War update", "source_excerpt": "community rescue"}
        score, reasons = news.score_item(item, ["community", "rescue"], ["war"])
        self.assertEqual(score, -100)
        self.assertIn("blocked:war", reasons)

    def test_blocked_words_do_not_match_inside_positive_words(self):
        item = {"title": "Community award success", "source_excerpt": "volunteer progress", "source_tier_bonus": 2}
        score, reasons = news.score_item(item, ["community", "success"], ["war"])
        self.assertGreater(score, 0)
        self.assertNotIn("blocked:war", reasons)

    def test_curated_source_still_requires_a_positive_signal(self):
        item = {"title": "Magazine subscription update", "source_excerpt": "Read our latest issue", "source_tier_bonus": 2}
        score, _ = news.score_item(item, ["community", "progress"], [])
        self.assertEqual(score, 0)

    def test_summary_is_reused_only_for_an_unchanged_source(self):
        item = {"title": "Progress", "source_excerpt": "A source excerpt", "published_at": "2026-07-15"}
        item["source_fingerprint"] = news.source_fingerprint(item)
        previous = {**item, "agent_summary": "En svensk sammanfattning."}
        self.assertEqual(news.reusable_summary(item, previous), "En svensk sammanfattning.")
        changed = {**item, "source_excerpt": "Updated source excerpt"}
        changed["source_fingerprint"] = news.source_fingerprint(changed)
        self.assertEqual(news.reusable_summary(changed, previous), "")

    def test_atomic_write_replaces_valid_json(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "news.json"
            news.atomic_json_write(path, {"items": ["åäö"]})
            self.assertIn("åäö", path.read_text(encoding="utf-8"))

    def test_total_feed_failure_keeps_the_last_good_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root / "feeds.json"
            output = root / "news.json"
            history = root / "history.json"
            config.write_text(json.dumps({
                "feeds": [{"name": "Broken", "url": "https://example.com/feed", "enabled": True}],
                "positive_keywords": ["progress"], "blocked_keywords": [], "minimum_score": 1,
            }), encoding="utf-8")
            original = {"generated_at": "earlier", "items": [{"id": "safe-copy"}]}
            output.write_text(json.dumps(original), encoding="utf-8")
            with patch.object(news, "fetch", side_effect=RuntimeError("offline")):
                result = news.main(["--force", "--config", str(config), "--output", str(output), "--history", str(history)])
            self.assertEqual(result, 1)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), original)


if __name__ == "__main__":
    unittest.main()
