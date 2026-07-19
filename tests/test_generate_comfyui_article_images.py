#!/usr/bin/env python3
"""Tests for generate_comfyui_article_images.py"""

import base64
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/generate_comfyui_article_images.py"
import importlib.util

SPEC = importlib.util.spec_from_file_location("generate_comfyui_article_images", MODULE_PATH)
cf = importlib.util.module_from_spec(SPEC)
sys.modules["generate_comfyui_article_images"] = cf
SPEC.loader.exec_module(cf)

HAVE_PIL = True
try:
    from PIL import Image
except ImportError:
    HAVE_PIL = False


def _webp_1280x848() -> bytes:
    """Create a minimal valid WebP container (VP8L, 1280x848)."""
    if HAVE_PIL:
        img = Image.new("RGB", (cf.WIDTH, cf.HEIGHT), color=(60, 120, 180))
        buf = io.BytesIO()
        img.save(buf, format="WEBP", lossless=True, method=6)
        return buf.getvalue()
    # Fallback: hand-crafted minimal VP8L WebP (1x1, scaled via metadata)
    # RIFF header
    riff = b"RIFF"
    size = (4 + 4 + 4 + 10 + 25)  # RIFF + WEBP + VP8L + data
    riff += size.to_bytes(4, "little")
    riff += b"WEBPVP8L"
    # VP8L header: 1 byte signature (0x2f) + 4 bytes size (width/height encoded)
    vp8l = b"\x2f"  # signature
    # width=1280, height=848, has_alpha=0, version=0
    vp8l += (1280 - 1).to_bytes(2, "little")
    vp8l += (848 - 1).to_bytes(2, "little")
    vp8l += b"\x00"  # has_alpha + version
    # Minimal compressed data (empty image)
    vp8l += b"\x00" * 20
    riff += len(vp8l).to_bytes(4, "little")
    riff += vp8l
    return riff


class ComfyUIImageTests(unittest.TestCase):
    def article(self, eligible=True, category="Natur"):
        return {
            "id": "0b87daf79218ce385c31",
            "title": "Testartikel om natur",
            "summary": "En fin sammanfattning om natur.",
            "category": category,
            "public_eligible": eligible,
            "source_image_verified": False,
        }

    @unittest.skipUnless(HAVE_PIL, "Pillow required")
    def test_generates_webp_and_metadata_from_comfyui(self):
        webp = _webp_1280x848()
        b64 = base64.b64encode(webp).decode()

        # Mock ComfyUI responses
        call_count = {"prompt": 0, "history": 0, "view": 0}

        def fake_opener(request, timeout=0):
            url = request.full_url if hasattr(request, "full_url") else request.get_full_url()
            call_count["total"] = call_count.get("total", 0) + 1
            if "/prompt" in url:
                call_count["prompt"] += 1
                return MagicMock(read=lambda n=-1: json.dumps({"prompt_id": "test-123"}).encode())
            if "/history/test-123" in url:
                call_count["history"] += 1
                if call_count["history"] < 2:
                    return MagicMock(read=lambda n=-1: json.dumps({}).encode())
                return MagicMock(read=lambda n=-1: json.dumps({
                    "test-123": {"outputs": {"11": {"images": [{"filename": "ljusglimt/article_test.webp", "subfolder": ""}]}}}
                }).encode())
            if "/view" in url:
                call_count["view"] += 1
                return MagicMock(read=lambda n=-1: webp)
            return MagicMock(read=lambda n=-1: b"{}")

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
            self.assertEqual(meta["model"], "comfyui-flux")
            self.assertEqual(meta["prompt_version"], cf.PROMPT_VERSION)

    @unittest.skipUnless(HAVE_PIL, "Pillow required")
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

    @unittest.skipUnless(HAVE_PIL, "Pillow required")
    def test_reuses_existing_valid_webp(self):
        webp = _webp_1280x848()
        sha = hashlib.sha256(webp).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            news = root / "news.json"
            item = self.article()
            item["ai_image"] = {
                "url": "/news-images/ai/articles/0b87daf79218ce385c31-abcdef1234567890abcd-v1.webp",
                "sha256": sha,
                "width": cf.WIDTH,
                "height": cf.HEIGHT,
                "model": "comfyui-flux",
                "prompt_version": cf.PROMPT_VERSION,
            }
            news.write_text(json.dumps({"items": [item]}), encoding="utf-8")
            output = root / "images"
            output.mkdir()
            expected_path = output / "0b87daf79218ce385c31-abcdef1234567890abcd-v1.webp"
            expected_path.write_bytes(webp)
            report = cf.process_news(
                news, output, account_id="acc", api_token="tok",
                max_images=1, opener=lambda *a, **k: None,
            )
            self.assertEqual(report.generated, 0)
            self.assertEqual(report.recovered, 1)


if __name__ == "__main__":
    unittest.main()