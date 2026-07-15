import base64
import hashlib
import importlib.util
import os
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/validate_generated_image_changes.py"
SPEC = importlib.util.spec_from_file_location("validate_generated_image_changes", MODULE_PATH)
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)

# A real, lossless 1280x848 WebP containing a single solid color. Keeping the
# fixture inline makes these tests independent of Pillow and other codecs.
VALID_WEBP = base64.b64decode(
    "UklGRlQAAABXRUJQVlA4TEgAAAAv/8TTAAfQ99LXu/8BBW3bMOUPvzuO6H+G//zn"
    "P//5z3/+85///Oc///nPf/7zn//85z//+c9//vOf//znP//5z3/+85///QA="
)


class GeneratedImageValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.article_dir = self.root / "public" / "news-images" / "ai" / "articles"
        self.article_dir.mkdir(parents=True)
        self.article_id = "0123456789abcdefabcd"
        self.fingerprint = "fedcba9876543210abcd"
        self.before = {
            "generated_at": "2026-07-15T00:00:00Z",
            "timezone": "Europe/Stockholm",
            "items": [{
                "id": self.article_id,
                "title": "A source-bound positive story",
                "source_fingerprint": self.fingerprint,
                "agent_summary": "",
                "public_eligible": True,
            }],
        }

    @property
    def filename(self):
        return f"{self.article_id}-{self.fingerprint[:8]}-v1.webp"

    @property
    def image_path(self):
        return self.article_dir / self.filename

    def write_image(self, payload=VALID_WEBP):
        self.image_path.write_bytes(payload)
        return payload

    def valid_ai_image(self, payload=VALID_WEBP):
        return {
            "url": f"/news-images/ai/articles/{self.filename}",
            "alt": "Redaktionell AI-illustration om en positiv nyhet.",
            "model": "gpt-image-2",
            "prompt_version": "editorial-concept-v1",
            "source_fingerprint": self.fingerprint,
            "width": 1280,
            "height": 848,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "generated_at": "2026-07-15T00:03:04.123456Z",
        }

    def changed_document(self, payload=VALID_WEBP):
        after = deepcopy(self.before)
        after["items"][0]["ai_image"] = self.valid_ai_image(payload)
        return after

    def test_accepts_one_valid_generated_image_change(self):
        self.write_image()
        validator.validate_generated_image_changes(self.before, self.changed_document(), self.article_dir)

    def test_accepts_no_image_changes(self):
        validator.validate_generated_image_changes(self.before, deepcopy(self.before), self.article_dir)

    def test_rejects_top_level_or_non_image_changes(self):
        after = deepcopy(self.before)
        after["generated_at"] = "2026-07-15T12:00:00Z"
        with self.assertRaisesRegex(ValueError, "top-level news metadata changed"):
            validator.validate_generated_image_changes(self.before, after, self.article_dir)

        after = deepcopy(self.before)
        after["items"][0]["title"] = "Changed source title"
        with self.assertRaisesRegex(ValueError, "non-image fields changed"):
            validator.validate_generated_image_changes(self.before, after, self.article_dir)

    def test_rejects_added_removed_or_reordered_articles(self):
        after = deepcopy(self.before)
        after["items"] = []
        with self.assertRaisesRegex(ValueError, "added or removed"):
            validator.validate_generated_image_changes(self.before, after, self.article_dir)

        second = deepcopy(self.before["items"][0])
        second["id"] = "11111111111111111111"
        before = deepcopy(self.before)
        before["items"].append(second)
        after = deepcopy(before)
        after["items"].reverse()
        with self.assertRaisesRegex(ValueError, "non-image fields changed"):
            validator.validate_generated_image_changes(before, after, self.article_dir)

    def test_rejects_more_than_three_changed_articles_before_touching_files(self):
        before = {"generated_at": "same", "items": []}
        after = {"generated_at": "same", "items": []}
        for number in range(4):
            article_id = f"{number:020x}"
            fingerprint = f"{number + 16:020x}"
            item = {"id": article_id, "source_fingerprint": fingerprint, "title": f"Story {number}"}
            before["items"].append(deepcopy(item))
            item["ai_image"] = {
                "url": f"/news-images/ai/articles/{article_id}-{fingerprint[:8]}-v1.webp",
                "alt": "AI illustration",
                "model": "gpt-image-2",
                "prompt_version": "editorial-concept-v1",
                "source_fingerprint": fingerprint,
                "width": 1280,
                "height": 848,
                "sha256": "0" * 64,
                "generated_at": "2026-07-15T00:00:00Z",
            }
            after["items"].append(item)
        with self.assertRaisesRegex(ValueError, "at most 3"):
            validator.validate_generated_image_changes(before, after, self.article_dir)

    def test_rejects_non_exact_ai_image_schema_and_removal(self):
        self.write_image()
        after = self.changed_document()
        after["items"][0]["ai_image"]["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "exactly the approved fields"):
            validator.validate_generated_image_changes(self.before, after, self.article_dir)

        before = self.changed_document()
        after = deepcopy(before)
        del after["items"][0]["ai_image"]
        with self.assertRaisesRegex(ValueError, "exactly the approved fields"):
            validator.validate_generated_image_changes(before, after, self.article_dir)

    def test_rejects_wrong_fixed_metadata(self):
        self.write_image()
        cases = {
            "model": "gpt-image-1",
            "prompt_version": "other-v1",
            "source_fingerprint": "0" * 20,
            "width": 1024,
            "height": True,
            "generated_at": "2026-07-15 00:00:00",
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                after = self.changed_document()
                after["items"][0]["ai_image"][field] = value
                with self.assertRaises(ValueError):
                    validator.validate_generated_image_changes(self.before, after, self.article_dir)

    def test_rejects_image_for_non_public_article(self):
        self.write_image()
        after = self.changed_document()
        after["items"][0]["public_eligible"] = False
        before = deepcopy(after)
        del before["items"][0]["ai_image"]
        with self.assertRaisesRegex(ValueError, "public_eligible"):
            validator.validate_generated_image_changes(before, after, self.article_dir)

    def test_rejects_non_exact_url_and_path_traversal(self):
        self.write_image()
        for url in (
            f"/news-images/ai/{self.filename}",
            f"/news-images/ai/articles/../{self.filename}",
            f"/news-images/ai/articles/{self.filename}?cache=1",
        ):
            with self.subTest(url=url):
                after = self.changed_document()
                after["items"][0]["ai_image"]["url"] = url
                with self.assertRaisesRegex(ValueError, "ai_image.url"):
                    validator.validate_generated_image_changes(self.before, after, self.article_dir)

    def test_rejects_missing_file_or_sha256_mismatch(self):
        with self.assertRaisesRegex(ValueError, "file is missing"):
            validator.validate_generated_image_changes(self.before, self.changed_document(), self.article_dir)

        self.write_image()
        after = self.changed_document()
        after["items"][0]["ai_image"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "does not match the file"):
            validator.validate_generated_image_changes(self.before, after, self.article_dir)

    def test_rejects_symlinked_image(self):
        real_image = self.root / "real.webp"
        real_image.write_bytes(VALID_WEBP)
        try:
            os.symlink(real_image, self.image_path)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks unavailable on this platform: {exc}")
        after = self.changed_document()
        with self.assertRaisesRegex(ValueError, "may not contain symlinks"):
            validator.validate_generated_image_changes(self.before, after, self.article_dir)

    def test_rejects_invalid_animated_or_wrong_size_webp(self):
        invalid_payloads = {
            "not-webp": b"not a webp",
            "truncated": VALID_WEBP[:-1],
            "animated": self._append_chunk(VALID_WEBP, b"ANIM", b"\x00" * 6),
            "wrong-size": self._change_vp8l_width(VALID_WEBP, 1279),
        }
        for label, payload in invalid_payloads.items():
            with self.subTest(label=label):
                self.write_image(payload)
                after = self.changed_document(payload)
                with self.assertRaises(ValueError):
                    validator.validate_generated_image_changes(self.before, after, self.article_dir)

    @staticmethod
    def _append_chunk(payload, fourcc, chunk):
        padding = b"\x00" if len(chunk) & 1 else b""
        body = payload[12:] + fourcc + len(chunk).to_bytes(4, "little") + chunk + padding
        return b"RIFF" + (len(body) + 4).to_bytes(4, "little") + b"WEBP" + body

    @staticmethod
    def _change_vp8l_width(payload, width):
        changed = bytearray(payload)
        chunk_index = changed.index(b"VP8L")
        header_index = chunk_index + 8
        bits = int.from_bytes(changed[header_index + 1:header_index + 5], "little")
        bits = (bits & ~0x3FFF) | (width - 1)
        changed[header_index + 1:header_index + 5] = bits.to_bytes(4, "little")
        return bytes(changed)


if __name__ == "__main__":
    unittest.main()
