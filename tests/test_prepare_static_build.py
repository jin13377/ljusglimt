import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEED_SLUG = "en-saker-slug"
ARTICLE_URL = f"https://ljusglimt.daniel-eklund1981.workers.dev/nyhet/{SEED_SLUG}"


class PrepareStaticBuildTests(unittest.TestCase):
    def run_build(self, seed_articles, news_items=None):
        temporary_directory = tempfile.TemporaryDirectory()
        base = Path(temporary_directory.name)
        output = base / "dist"
        data = base / "data"
        output.mkdir()
        data.mkdir()
        (output / "index.html").write_text(
            """<!doctype html><html lang=\"sv\"><head>
<title>Ljusglimt – positiva nyheter som ger perspektiv</title>
<meta name=\"description\" content=\"Standardbeskrivning\">
<link rel=\"canonical\" href=\"https://ljusglimt.daniel-eklund1981.workers.dev/\">
</head><body><div id=\"root\"></div><script type=\"module\" src=\"/assets/app.js\"></script></body></html>""",
            encoding="utf-8",
        )
        (data / "seed-news.json").write_text(json.dumps({"articles": seed_articles}), encoding="utf-8")
        (data / "news.json").write_text(json.dumps({"items": news_items or []}), encoding="utf-8")
        environment = os.environ.copy()
        environment["LJUSGLIMT_DIST_DIR"] = str(output)
        environment["LJUSGLIMT_DATA_DIR"] = str(data)
        result = subprocess.run(
            ["node", "scripts/prepare_static_build.mjs"],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
        )
        return temporary_directory, output, result

    @staticmethod
    def valid_seed(**overrides):
        article = {
            "slug": SEED_SLUG,
            "title": "En säker <nyhet>",
            "summary": "En sammanfattning med <tecken>.",
            "publishedAt": "2026-07-18T10:00:00Z",
            "category": "Framsteg",
            "source": {"name": "Källan", "url": "https://example.com/article"},
        }
        article.update(overrides)
        return article

    def test_generates_safe_server_readable_article_html(self):
        temporary_directory, output, result = self.run_build([self.valid_seed()])
        with temporary_directory:
            self.assertEqual(result.returncode, 0, result.stderr)
            article_path = output / "seo" / "articles" / f"{SEED_SLUG}.html"
            self.assertTrue(article_path.is_file())
            article_html = article_path.read_text(encoding="utf-8")
            self.assertIn("<h1>En säker &lt;nyhet&gt;</h1>", article_html)
            self.assertIn(f'<link rel="canonical" href="{ARTICLE_URL}">', article_html)
            self.assertIn('<script type="application/ld+json" data-ljusglimt-jsonld="true">', article_html)
            self.assertIn('"@type":"NewsArticle"', article_html)
            self.assertIn('src="/assets/app.js"', article_html)
            self.assertNotIn('<link rel="canonical" href="https://ljusglimt.daniel-eklund1981.workers.dev/">', article_html)

    def test_rejects_traversal_and_duplicate_slugs_before_article_writes(self):
        for articles in (
            [self.valid_seed(slug="../../escape")],
            [self.valid_seed(), self.valid_seed(title="En annan titel")],
            [self.valid_seed(title=None)],
        ):
            with self.subTest(articles=articles):
                temporary_directory, output, result = self.run_build(articles)
                with temporary_directory:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse((output / "seo" / "articles").exists())

    def test_unsafe_source_url_is_rendered_as_text_not_a_link(self):
        temporary_directory, output, result = self.run_build([
            self.valid_seed(source={"name": "Källan", "url": "javascript:alert(1)"})
        ])
        with temporary_directory:
            self.assertEqual(result.returncode, 0, result.stderr)
            article_path = output / "seo" / "articles" / f"{SEED_SLUG}.html"
            self.assertTrue(article_path.is_file())
            article_html = article_path.read_text(encoding="utf-8")
            self.assertNotIn("javascript:", article_html)
            self.assertIn("<p>Källa: Källan</p>", article_html)

    def test_fetched_image_selection_matches_frontend_priority(self):
        article_id = "a" * 20
        fingerprint = "b" * 20
        ai_url = f"/news-images/ai/articles/{article_id}-{fingerprint[:8]}-v1.webp"
        generated_url = f"/news-images/generated/{article_id}-{fingerprint[:8]}-v1.svg"
        fetched = {
            "id": article_id,
            "title": "Fetched title",
            "display_title_sv": "Svensk rubrik",
            "agent_summary": "Svensk sammanfattning.",
            "published_at": "2026-07-18T10:00:00Z",
            "public_eligible": True,
            "source": "UN News",
            "url": "https://example.com/fetched",
            "source_fingerprint": fingerprint,
            "source_image_verified": True,
            "source_image_url": "https://example.com/unlicensed.jpg",
            "ai_image": {
                "url": ai_url,
                "source_fingerprint": fingerprint,
                "model": "gpt-image-2",
                "prompt_version": "editorial-concept-v1",
                "width": 1280,
                "height": 848,
                "sha256": "c" * 64,
                "alt": "AI-bild",
                "generated_at": "2026-07-18T10:00:00Z",
            },
            "generated_image": {
                "url": generated_url,
                "source_fingerprint": fingerprint,
                "style_version": "glimt-abstract-v1",
                "width": 1280,
                "height": 848,
                "sha256": "d" * 64,
                "alt": "Automatisk bild",
            },
        }
        temporary_directory, output, result = self.run_build([], [fetched])
        with temporary_directory:
            self.assertEqual(result.returncode, 0, result.stderr)
            slug = f"fetched-title-{article_id[:6]}"
            article_path = output / "seo" / "articles" / f"{slug}.html"
            self.assertTrue(article_path.is_file())
            article_html = article_path.read_text(encoding="utf-8")
            self.assertIn(ai_url, article_html)
            self.assertNotIn(generated_url, article_html)
            self.assertNotIn("unlicensed.jpg", article_html)


if __name__ == "__main__":
    unittest.main()
