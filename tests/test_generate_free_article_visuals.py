import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/generate_free_article_visuals.py"
SPEC = importlib.util.spec_from_file_location("generate_free_article_visuals", MODULE_PATH)
visuals = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(visuals)


class FreeArticleVisualTests(unittest.TestCase):
    def article(self, eligible=True):
        return {
            "id": "0123456789abcdefabcd",
            "title": "Untrusted <script>alert(1)</script> source title",
            "source_fingerprint": "fedcba9876543210abcd",
            "public_eligible": eligible,
        }

    def test_creates_deterministic_text_free_svg_and_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            news = root / "news.json"
            news.write_text(json.dumps({"items": [self.article()]}), encoding="utf-8")
            output = root / "images"
            result = visuals.process(news, output)
            saved = json.loads(news.read_text(encoding="utf-8"))["items"][0]
            path = output / "0123456789abcdefabcd-fedcba98-v1.svg"
            payload = path.read_bytes()
            self.assertEqual(result, (1, 0, 0))
            self.assertNotIn(b"<text", payload.lower())
            self.assertNotIn(b"<script", payload.lower())
            self.assertNotIn(b"Untrusted", payload)
            self.assertEqual(saved["generated_image"]["sha256"], hashlib.sha256(payload).hexdigest())
            first_payload = payload
            self.assertEqual(visuals.process(news, output), (0, 1, 0))
            self.assertEqual(path.read_bytes(), first_payload)

    def test_skips_ineligible_articles(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            news = root / "news.json"
            news.write_text(json.dumps({"items": [self.article(False)]}), encoding="utf-8")
            self.assertEqual(visuals.process(news, root / "images"), (0, 0, 1))
            self.assertFalse(list((root / "images").glob("*.svg")))

    def test_source_backed_article_does_not_get_an_illustration(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            article = self.article()
            article["source_image_verified"] = True
            article["generated_image"] = {"stale": True}
            news = root / "news.json"
            news.write_text(json.dumps({"items": [article]}), encoding="utf-8")
            self.assertEqual(visuals.process(news, root / "images"), (0, 0, 1))
            saved = json.loads(news.read_text(encoding="utf-8"))["items"][0]
            self.assertNotIn("generated_image", saved)
            self.assertFalse(list((root / "images").glob("*.svg")))

    def test_rejects_invalid_source_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            article = self.article()
            article["id"] = "../bad"
            news = root / "news.json"
            news.write_text(json.dumps({"items": [article]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "20 lowercase hex"):
                visuals.process(news, root / "images")

    def test_paper_collage_style_has_category_motifs(self):
        motif_markers = {
            "Natur": b'data-collage-motif="natur"',
            "Teknik": b'data-collage-motif="teknik"',
        }
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            items = []
            for index, (category, _) in enumerate(motif_markers.items()):
                article = self.article()
                article["id"] = ["0123456789abcdef0123", "0123456789abcdef4567"][index]
                article["category"] = category
                items.append(article)
            news = root / "news.json"
            news.write_text(json.dumps({"items": items}), encoding="utf-8")
            output = root / "images"
            visuals.process(news, output)
            saved = json.loads(news.read_text(encoding="utf-8"))["items"]
            payloads = []
            for item in saved:
                path = output / item["generated_image"]["url"].split("/")[-1]
                payload = path.read_bytes()
                self.assertIn(b'data-collage-motif', payload)
                self.assertIn(b"polygon", payload)
                self.assertNotIn(b"<text", payload.lower())
                self.assertNotIn(b"<script", payload.lower())
                payloads.append(payload)
            for category, marker in motif_markers.items():
                self.assertIn(marker, payloads[list(motif_markers).index(category)])
            self.assertNotEqual(payloads[0], payloads[1])


if __name__ == "__main__":
    unittest.main()
