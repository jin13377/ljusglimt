import importlib.util
import unittest
from copy import deepcopy
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/validate_agent_news_changes.py"
SPEC = importlib.util.spec_from_file_location("validate_agent_news_changes", MODULE_PATH)
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class AgentNewsValidationTests(unittest.TestCase):
    def setUp(self):
        self.before = {
            "generated_at": "2026-07-15T00:00:00Z",
            "items": [{
                "id": "article-1",
                "title": "Source title",
                "url": "https://example.com/story",
                "agent_summary": "",
            }],
        }

    def test_accepts_a_new_summary_only(self):
        after = deepcopy(self.before)
        after["items"][0]["agent_summary"] = "En kort svensk sammanfattning."
        validator.validate_news_changes(self.before, after)

    def test_rejects_changed_source_fields(self):
        after = deepcopy(self.before)
        after["items"][0]["title"] = "Altered title"
        with self.assertRaisesRegex(ValueError, "source fields changed"):
            validator.validate_news_changes(self.before, after)

    def test_rejects_removed_articles(self):
        after = deepcopy(self.before)
        after["items"] = []
        with self.assertRaisesRegex(ValueError, "added or removed"):
            validator.validate_news_changes(self.before, after)

    def test_rejects_overwriting_an_existing_summary(self):
        before = deepcopy(self.before)
        before["items"][0]["agent_summary"] = "Redan granskad text."
        after = deepcopy(before)
        after["items"][0]["agent_summary"] = "Ersatt text."
        with self.assertRaisesRegex(ValueError, "existing summary changed"):
            validator.validate_news_changes(before, after)


if __name__ == "__main__":
    unittest.main()
