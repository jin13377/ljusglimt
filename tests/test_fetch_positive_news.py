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

    def test_rss_source_image_requires_explicit_policy_host_credit_and_license(self):
        xml = b"""<rss xmlns:media="http://search.yahoo.com/mrss/">
        <channel><item><title>Community rescue success</title>
        <link>https://example.com/story</link><description>Volunteers helped.</description>
        <media:content url="https://cdn.example.com/photo.jpg" type="image/jpeg">
          <media:title>Volunteers celebrate</media:title>
          <media:credit role="photographer">Ada Example</media:credit>
          <media:license href="https://creativecommons.org/licenses/by/4.0/" />
        </media:content></item></channel></rss>"""
        policy = {
            "enabled": True,
            "allowed_image_hosts": ["cdn.example.com"],
            "allowed_license_urls": ["https://creativecommons.org/licenses/by/4.0/"],
        }
        image = news.parse_feed(xml, "Example", "en", policy)[0]
        self.assertTrue(image["source_image_verified"])
        self.assertEqual(image["source_image_credit"], "Ada Example")
        self.assertEqual(image["source_image_license_id"], "CC-BY-4.0")
        self.assertEqual(image["source_image_source_url"], "https://example.com/story")
        self.assertEqual(image["source_image_verification_method"], "rss-license-v1")

        self.assertNotIn("source_image_verified", news.parse_feed(xml, "Example", "en")[0])
        no_license_policy = {"enabled": True, "allowed_image_hosts": ["cdn.example.com"]}
        self.assertNotIn("source_image_verified", news.parse_feed(xml, "Example", "en", no_license_policy)[0])
        wrong_license_policy = {
            "enabled": True,
            "allowed_image_hosts": ["cdn.example.com"],
            "allowed_license_urls": ["https://creativecommons.org/publicdomain/zero/1.0/"],
        }
        self.assertNotIn("source_image_verified", news.parse_feed(xml, "Example", "en", wrong_license_policy)[0])
        wrong_host = {
            "enabled": True,
            "allowed_image_hosts": ["other.example.com"],
            "allowed_license_urls": ["https://creativecommons.org/licenses/by/4.0/"],
        }
        self.assertNotIn("source_image_verified", news.parse_feed(xml, "Example", "en", wrong_host)[0])

    def test_rss_source_image_rejects_missing_or_unsupported_rights_metadata(self):
        policy = {
            "enabled": True,
            "allowed_image_hosts": ["cdn.example.com"],
            "allowed_license_urls": ["https://creativecommons.org/licenses/by/4.0/"],
        }
        templates = (
            "<media:license href='https://creativecommons.org/licenses/by/4.0/' />",
            "<media:credit>Ada Example</media:credit>",
            "<media:credit>Ada Example</media:credit><media:license href='https://creativecommons.org/licenses/by-nc/4.0/' />",
        )
        for metadata in templates:
            with self.subTest(metadata=metadata):
                xml = f"""<rss xmlns:media="http://search.yahoo.com/mrss/"><channel><item>
                <title>Community rescue success</title><link>https://example.com/story</link>
                <description>Volunteers helped.</description>
                <media:content url="https://cdn.example.com/photo.jpg" medium="image">
                {metadata}</media:content></item></channel></rss>""".encode()
                self.assertNotIn("source_image_verified", news.parse_feed(xml, "Example", "en", policy)[0])

    def test_allowlisted_feed_thumbnail_is_accepted_as_source_media(self):
        xml = b"""<rss xmlns:media="http://search.yahoo.com/mrss/"><channel><item>
        <title>Adorable puppy finds a best friend</title>
        <link>https://example.com/animals/friends</link><description>A happy friendship.</description>
        <media:thumbnail url="https://images.example.com/puppy.jpg" />
        </item></channel></rss>"""
        policy = {
            "enabled": True,
            "mode": "feed-thumbnail",
            "allowed_article_hosts": ["example.com"],
            "allowed_image_hosts": ["images.example.com"],
            "credit": "Example Animals",
        }
        item = news.parse_feed(xml, "Example Animals", "en", policy)[0]
        self.assertTrue(item["source_image_verified"])
        self.assertEqual(item["source_image_credit"], "Example Animals")
        self.assertEqual(item["source_image_rights_url"], "https://example.com/animals/friends")
        self.assertEqual(item["source_image_verification_method"], "rss-syndicated-thumbnail-v1")

        wrong_host = {**policy, "allowed_article_hosts": ["other.example.com"]}
        self.assertNotIn("source_image_verified", news.parse_feed(xml, "Example Animals", "en", wrong_host)[0])

    def test_youtube_atom_entry_gets_safe_privacy_enhanced_video(self):
        xml = b"""<feed xmlns="http://www.w3.org/2005/Atom"
          xmlns:yt="http://www.youtube.com/xml/schemas/2015"
          xmlns:media="http://search.yahoo.com/mrss/"><entry>
          <yt:videoId>PahtM3xtRus</yt:videoId>
          <title>Adorable animals become best friends</title>
          <link rel="alternate" href="https://www.youtube.com/watch?v=PahtM3xtRus" />
          <published>2026-07-15T21:00:30+00:00</published>
          <media:group><media:description>A happy friendship.</media:description>
          <media:thumbnail url="https://i1.ytimg.com/vi/PahtM3xtRus/hqdefault.jpg" /></media:group>
        </entry></feed>"""
        image_policy = {
            "enabled": True, "mode": "feed-thumbnail",
            "allowed_article_hosts": ["www.youtube.com"],
            "allowed_image_hosts": ["i1.ytimg.com"], "credit": "The Dodo",
        }
        video_policy = {"enabled": True, "provider": "youtube"}
        item = news.parse_feed(xml, "The Dodo", "en", image_policy, video_policy)[0]
        self.assertTrue(item["source_image_verified"])
        self.assertEqual(item["source_video"]["video_id"], "PahtM3xtRus")
        self.assertEqual(item["source_video"]["embed_url"], "https://www.youtube-nocookie.com/embed/PahtM3xtRus")

    def test_regular_news_rss_gets_safe_youtube_video_from_media_metadata(self):
        xml = b"""<rss xmlns:media="http://search.yahoo.com/mrss/"><channel><item>
        <title>NASA flight innovation accelerates research</title>
        <link>https://www.nasa.gov/example/flight-innovation/</link>
        <description>A new research platform advances knowledge.</description>
        <media:content url="https://www.youtube.com/embed/Fb08ooo7MhI" medium="video" />
        <media:player url="https://www.youtube.com/embed/Fb08ooo7MhI" />
        </item></channel></rss>"""
        policy = {"enabled": True, "providers": ["youtube", "dailymotion"]}
        item = news.parse_feed(xml, "NASA News Releases", "en", video_policy=policy)[0]
        self.assertEqual(item["url"], "https://www.nasa.gov/example/flight-innovation")
        self.assertEqual(item["source_video"]["provider"], "youtube")
        self.assertEqual(item["source_video"]["video_id"], "Fb08ooo7MhI")
        self.assertEqual(item["source_video"]["source_url"], "https://www.youtube.com/watch?v=Fb08ooo7MhI")

        lookalike = xml.replace(b"www.youtube.com", b"www.youtube.com.evil.example")
        self.assertNotIn(
            "source_video",
            news.parse_feed(lookalike, "NASA News Releases", "en", video_policy=policy)[0],
        )

    def test_source_video_is_reused_only_for_unchanged_source(self):
        item = {"title": "Flight innovation", "source_excerpt": "Research advances.", "published_at": "2026-07-16"}
        item["source_fingerprint"] = news.source_fingerprint(item)
        previous = {
            **item,
            "source_video": {
                "provider": "youtube",
                "video_id": "Fb08ooo7MhI",
                "embed_url": "https://www.youtube-nocookie.com/embed/Fb08ooo7MhI",
                "source_url": "https://www.youtube.com/watch?v=Fb08ooo7MhI",
                "title": "Flight innovation",
            },
        }
        self.assertEqual(news.reusable_source_video(item, previous)["source_video"]["video_id"], "Fb08ooo7MhI")
        changed = {**item, "source_excerpt": "Changed source text."}
        changed["source_fingerprint"] = news.source_fingerprint(changed)
        self.assertEqual(news.reusable_source_video(changed, previous), {})

    def test_dailymotion_listing_gets_source_image_and_video(self):
        payload = json.dumps({"list": [{
            "id": "xamx6nm", "title": "Boyfriend Has Best Reaction To Surprise Foster Kittens",
            "description": "A joyful surprise with kittens.",
            "thumbnail_720_url": "https://s2.dmcdn.net/v/example/x720",
            "url": "https://www.dailymotion.com/video/xamx6nm", "created_time": 1783521247,
        }]}).encode()
        image_policy = {
            "enabled": True, "mode": "feed-thumbnail", "allowed_article_hosts": ["www.dailymotion.com"],
            "allowed_image_hosts": ["s2.dmcdn.net"], "credit": "The Dodo",
        }
        video_policy = {"enabled": True, "provider": "dailymotion"}
        item = news.parse_dailymotion_feed(payload, "The Dodo", "en", image_policy, video_policy)[0]
        self.assertTrue(item["source_image_verified"])
        self.assertEqual(item["source_video"]["provider"], "dailymotion")
        self.assertEqual(item["source_video"]["embed_url"], "https://geo.dailymotion.com/player.html?video=xamx6nm")
        self.assertEqual(item["source_image_credit"], "The Dodo")

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

    def test_public_eligible_matches_frontend_rules(self):
        cases = (
            ({"title": "Community rescue success", "source_excerpt": "Volunteers helped."}, True),
            ({"title": "Could this rescue succeed?", "source_excerpt": "Volunteers helped."}, False),
            ({"title": "Rescue success after bloody injury", "source_excerpt": "Volunteers helped."}, False),
            ({"title": "Rescue from a crab trap", "source_excerpt": "The animal was in distress."}, False),
            ({"title": "A stranded animal needed help", "source_excerpt": "It was unable to move."}, False),
            ({"title": "Community rescue success", "source_excerpt": "Appeared first on Example."}, False),
            ({"title": "Community update", "source_excerpt": "A normal update."}, False),
            ({"title": "Community update", "source_excerpt": "A rescue success.", "agent_summary": "En neutral notis."}, True),
            ({"title": "Flight innovation accelerates research", "source_excerpt": "A practical platform."}, True),
            ({"title": "Community rescue success", "source_excerpt": "Volunteers helped.", "language": "en"}, False),
            ({"title": "Community rescue success", "source_excerpt": "Volunteers helped.", "language": "en",
              "display_title_sv": "Framgång för lokal räddningsinsats", "agent_summary": "Volontärer hjälpte till."}, True),
        )
        for item, expected in cases:
            with self.subTest(title=item["title"]):
                self.assertEqual(news.public_eligible(item), expected)

    def test_summary_is_reused_only_for_an_unchanged_source(self):
        item = {"title": "Progress", "source_excerpt": "A source excerpt", "published_at": "2026-07-15"}
        item["source_fingerprint"] = news.source_fingerprint(item)
        previous = {**item, "agent_summary": "En svensk sammanfattning."}
        self.assertEqual(news.reusable_summary(item, previous), "En svensk sammanfattning.")
        changed = {**item, "source_excerpt": "Updated source excerpt"}
        changed["source_fingerprint"] = news.source_fingerprint(changed)
        self.assertEqual(news.reusable_summary(changed, previous), "")

    def test_curated_swedish_copy_requires_matching_source_fingerprint(self):
        item = {"id": "a" * 20, "source_fingerprint": "b" * 20}
        catalog = {"items": {"a" * 20: {
            "source_fingerprint": "b" * 20,
            "title": "En svensk rubrik",
            "summary": "En kort svensk sammanfattning.",
        }}}
        self.assertEqual(news.curated_swedish_copy(item, catalog), {
            "display_title_sv": "En svensk rubrik",
            "agent_summary": "En kort svensk sammanfattning.",
        })
        self.assertEqual(news.curated_swedish_copy(
            {**item, "source_fingerprint": "c" * 20}, catalog,
        ), {})

    def test_verified_source_image_is_reused_only_for_unchanged_source(self):
        item = {"title": "Progress", "source_excerpt": "A source excerpt", "published_at": "2026-07-15"}
        item["source_fingerprint"] = news.source_fingerprint(item)
        previous = {
            **item,
            "source_image_verified": True,
            "source_image_url": "https://images.example.com/progress.jpg",
            "source_image_alt": "A verified source image",
            "source_image_credit": "Photo: Example",
            "source_image_rights_url": "https://example.com/rights",
        }
        self.assertEqual(news.reusable_source_image(item, previous)["source_image_credit"], "Photo: Example")
        changed = {**item, "source_excerpt": "Changed excerpt"}
        changed["source_fingerprint"] = news.source_fingerprint(changed)
        self.assertEqual(news.reusable_source_image(changed, previous), {})
        self.assertEqual(news.reusable_source_image(item, {**previous, "source_image_rights_url": ""}), {})

    def test_ai_image_is_reused_only_when_nested_schema_and_fingerprint_are_valid(self):
        item = {"id": "a" * 20, "source_fingerprint": "b" * 20}
        image = {
            "url": f"/news-images/ai/articles/{'a' * 20}-{'b' * 8}-v1.webp",
            "alt": "Redaktionell AI-illustration om lokalt samarbete.",
            "model": "gpt-image-2",
            "prompt_version": "editorial-concept-v1",
            "source_fingerprint": "b" * 20,
            "width": 1280,
            "height": 848,
            "sha256": "c" * 64,
            "generated_at": "2026-07-15T12:00:00Z",
        }
        previous = {"source_fingerprint": "b" * 20, "ai_image": image}
        self.assertEqual(news.reusable_ai_image(item, previous), {"ai_image": image})

        invalid_images = (
            {**image, "model": "another-model"},
            {**image, "sha256": "not-a-hash"},
            {**image, "url": "/news-images/ai/articles/wrong.webp"},
            {**image, "extra": "not-allowed"},
        )
        for invalid in invalid_images:
            with self.subTest(invalid=invalid):
                self.assertEqual(news.reusable_ai_image(item, {**previous, "ai_image": invalid}), {})
        changed = {**item, "source_fingerprint": "d" * 20}
        self.assertEqual(news.reusable_ai_image(changed, previous), {})

    def test_free_generated_image_is_reused_only_for_unchanged_source(self):
        item = {"id": "a" * 20, "source_fingerprint": "b" * 20}
        image = {
            "url": f"/news-images/generated/{'a' * 20}-{'b' * 8}-v1.svg",
            "alt": "Automatiskt skapad redaktionell illustration.",
            "style_version": "glimt-abstract-v1",
            "source_fingerprint": "b" * 20,
            "width": 1280,
            "height": 848,
            "sha256": "c" * 64,
        }
        previous = {"source_fingerprint": "b" * 20, "generated_image": image}
        self.assertEqual(news.reusable_generated_image(item, previous), {"generated_image": image})
        self.assertEqual(news.reusable_generated_image(
            {**item, "source_fingerprint": "d" * 20}, previous), {})
        self.assertEqual(news.reusable_generated_image(
            item, {**previous, "generated_image": {**image, "style_version": "wrong"}}), {})

    def test_fresh_licensed_rss_image_wins_over_previous_image(self):
        xml = b"""<rss xmlns:media="http://search.yahoo.com/mrss/"><channel><item>
        <title>Community rescue success</title><link>https://example.com/story</link>
        <description>Volunteers helped.</description>
        <media:content url="https://cdn.example.com/new.jpg" medium="image">
          <media:credit>Ada Example</media:credit>
          <media:license href="https://creativecommons.org/publicdomain/zero/1.0/" />
        </media:content></item></channel></rss>"""
        parsed = news.parse_feed(
            xml, "Example", "en",
            {
                "enabled": True,
                "allowed_image_hosts": ["cdn.example.com"],
                "allowed_license_urls": ["https://creativecommons.org/publicdomain/zero/1.0/"],
            },
        )[0]
        previous = {
            **parsed,
            "source_image_url": "https://old.example.com/old.jpg",
            "source_image_credit": "Old credit",
            "source_image_rights_url": "https://old.example.com/rights",
        }
        if parsed.get("source_image_verified") is not True:
            parsed.update(news.reusable_source_image(parsed, previous))
        self.assertEqual(parsed["source_image_url"], "https://cdn.example.com/new.jpg")
        self.assertEqual(parsed["source_image_license_id"], "CC0-1.0")

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

    def test_one_failed_feed_keeps_its_last_published_items(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root / "feeds.json"
            output = root / "news.json"
            history = root / "history.json"
            config.write_text(json.dumps({
                "feeds": [
                    {"name": "Temporarily offline", "url": "https://offline.example/feed", "base_score": 2},
                    {"name": "Working", "url": "https://working.example/feed", "base_score": 2},
                ],
                "positive_keywords": ["friend", "community", "rescue"],
                "blocked_keywords": [], "minimum_score": 1, "max_items": 10,
            }), encoding="utf-8")
            old_item = {
                "id": "a" * 20, "title": "Adorable kitten finds a best friend",
                "url": "https://offline.example/story", "source": "Temporarily offline",
                "language": "en", "source_excerpt": "A happy friendship.",
                "agent_summary": "", "source_fingerprint": "b" * 20,
                "positivity_score": 5, "positive_signals": ["friend"], "public_eligible": True,
            }
            output.write_text(json.dumps({"items": [old_item]}), encoding="utf-8")
            working_xml = b"""<rss><channel><item><title>Community rescue success</title>
            <link>https://working.example/story</link><description>Friends helped.</description></item></channel></rss>"""

            def fake_fetch(url, *_args):
                if "offline" in url:
                    raise RuntimeError("temporary outage")
                return working_xml

            with patch.object(news, "fetch", side_effect=fake_fetch):
                self.assertEqual(news.main(["--force", "--config", str(config), "--output", str(output), "--history", str(history)]), 0)
            saved = json.loads(output.read_text(encoding="utf-8"))["items"]
            self.assertEqual({item["source"] for item in saved}, {"Temporarily offline", "Working"})


if __name__ == "__main__":
    unittest.main()
