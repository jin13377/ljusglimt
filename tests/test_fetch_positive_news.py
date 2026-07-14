import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/fetch_positive_news.py"
SPEC = importlib.util.spec_from_file_location("fetch_positive_news", MODULE_PATH)
news = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(news)


class PositiveNewsTests(unittest.TestCase):
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

    def test_atomic_write_replaces_valid_json(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "news.json"
            news.atomic_json_write(path, {"items": ["åäö"]})
            self.assertIn("åäö", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
