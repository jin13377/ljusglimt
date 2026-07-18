import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/generate_cf_article_images.py"
SPEC = importlib.util.spec_from_file_location("generate_cf_article_images", MODULE_PATH)
cf = importlib.util.module_from_spec(SPEC)
sys.modules["generate_cf_article_images"] = cf
SPEC.loader.exec_module(cf)

try:
    from PIL import Image
    HAVE_PIL = True
except Exception:  # pragma: no cover
    HAVE_PIL = False


def _png_1024() -> bytes:
    im = Image.new("RGB", (1024, 1024), (120, 160, 90))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


class FakeResponse:
    def __init__(self, payload: bytes, status: int = 200):
        self._payload = payload
        self.status = status

    def read(self, *_a):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class CfArticleImageTests(unittest.TestCase):
    def article(self, eligible=True):
        return {
            "id": "0123456789abcdefabcd",
            "title": "A hopeful <script>bad</script> headline",
            "source_fingerprint": "fedcba9876543210abcd",
            "public_eligible": eligible,
            "category": "Djur",
        }

    @unittest.skipUnless(HAVE_PIL, "Pillow required")
    def test_generates_webp_and_metadata_from_cf(self):
        png = _png_1024()
        b64 = cf.base64.b64encode(png).decode()

        def fake_opener(request, timeout=0):
            body = json.loads(request.data.decode())
            # prompt must NOT leak raw untrusted title verbatim as an instruction
            self.assertIn("prompt", body)
            self.assertNotIn("<script>", body["prompt"])
            return FakeResponse(json.dumps({"success": True, "result": {"image": b64}}).encode())

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            news = root / "news.json"
            news.write_text(json.dumps({"items": [self.article()]}), encoding="utf-8")
            output = root / "images"
            report = cf.process_news(
                news, output, account_id="acc", api_token="tok",
                max_images=1, opener=fake_opener,
            )
            self.assertEqual(report.generated, 1)
            saved = json.loads(news.read_text(encoding="utf-8"))["items"][0]
            meta = saved["ai_image"]
            path = output / meta["url"].split("/")[-1]
            data = path.read_bytes()
            self.assertTrue(meta["url"].startswith("/news-images/ai/articles/"))
            self.assertEqual(meta["width"], cf.WIDTH)
            self.assertEqual(meta["height"], cf.HEIGHT)
            self.assertEqual(meta["sha256"], hashlib.sha256(data).hexdigest())
            self.assertIn(cf.MODEL_TAG, meta["model"])
            # verify it is a real 1280x848 webp
            dims = cf.validate_webp(data)
            self.assertEqual(dims, (cf.WIDTH, cf.HEIGHT))
            # second run reuses (no regeneration)
            report2 = cf.process_news(
                news, output, account_id="acc", api_token="tok",
                max_images=1, opener=fake_opener,
            )
            self.assertEqual(report2.generated, 0)

    def test_skips_when_no_eligible_items(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            news = root / "news.json"
            news.write_text(json.dumps({"items": [self.article(eligible=False)]}), encoding="utf-8")
            report = cf.process_news(
                news, root / "images", account_id="acc", api_token="tok",
                max_images=1, opener=lambda *a, **k: None,
            )
            self.assertEqual(report.selected, 0)
            self.assertEqual(report.generated, 0)

    def test_requires_credentials_when_work_pending(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            news = root / "news.json"
            news.write_text(json.dumps({"items": [self.article()]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                cf.process_news(
                    news, root / "images", account_id="", api_token="",
                    max_images=1, opener=lambda *a, **k: None,
                )


    @unittest.skipUnless(HAVE_PIL, "Pillow required")
    def test_stop_whole_run_on_rate_limit(self):
        # Both models 429 -> the run must stop (0 generated), not
        # burn attempts on a fallback or starve other articles.
        class Resp429:
            status = 429

            def read(self, n=-1):
                return b'{"success":false,"errors":[{"message":"rate limited"}]}'

        def fake_opener(request, timeout=0):
            raise urllib.error.HTTPError(str(request.full_url), 429, "rate", {}, Resp429())

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            news = root / "news.json"
            items = [self.article(), self.article(eligible=False)]
            news.write_text(json.dumps({"items": items}), encoding="utf-8")
            report = cf.process_news(
                news, root / "images", account_id="acc", api_token="tok",
                max_images=1, opener=fake_opener,
            )
            self.assertEqual(report.generated, 0)
            self.assertEqual(report.failed, 0)
            self.assertTrue(any("rate" in e.lower() for e in report.errors))


if __name__ == "__main__":
    unittest.main()
