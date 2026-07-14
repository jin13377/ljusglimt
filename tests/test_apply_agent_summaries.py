import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("apply_agent_summaries", SCRIPTS / "apply_agent_summaries.py")
apply = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(apply)


class ApplySummariesTests(unittest.TestCase):
    def test_only_summary_changes(self):
        news = {"items": [{"id": "one", "title": "Original", "url": "https://example.com", "agent_summary": ""}]}
        updated, count = apply.apply_summaries(news, {"summaries": {"one": "  Kort   text. "}})
        self.assertEqual(count, 1)
        self.assertEqual(updated["items"][0]["title"], "Original")
        self.assertEqual(updated["items"][0]["url"], "https://example.com")
        self.assertEqual(updated["items"][0]["agent_summary"], "Kort text.")

    def test_rejects_oversized_summary(self):
        with self.assertRaises(ValueError):
            apply.apply_summaries({"items": [{"id": "one"}]}, {"summaries": {"one": "x" * 501}})


if __name__ == "__main__":
    unittest.main()
