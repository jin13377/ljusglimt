import http.client
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

import server


class AccountApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.original_db = server.DB_FILE
        cls.original_seed = server.FORUM_SEED
        server.DB_FILE = Path(cls.temp.name) / "test.db"
        server.FORUM_SEED = Path(cls.temp.name) / "missing.json"
        server._rate_state.clear()
        server.init_db()
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        server.DB_FILE = cls.original_db
        server.FORUM_SEED = cls.original_seed
        cls.temp.cleanup()

    def request(self, method, path, payload=None, cookie=None, extra_headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Origin": f"http://127.0.0.1:{self.port}"}
        body = None
        if payload is not None:
            body = json.dumps(payload)
            headers["Content-Type"] = "application/json"
        if cookie:
            headers["Cookie"] = cookie
        headers.update(extra_headers or {})
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        data = json.loads(response.read().decode("utf-8"))
        result = response.status, data, response.getheader("Set-Cookie")
        connection.close()
        return result

    def test_registration_saved_article_and_pending_forum(self):
        status, data, cookie_header = self.request("POST", "/api/auth/register", {
            "name": "Testperson", "email": "test@example.com", "password": "säkertlösenord"
        })
        self.assertEqual(status, 201)
        self.assertEqual(data["user"]["name"], "Testperson")
        cookie = cookie_header.split(";", 1)[0]

        status, data, _ = self.request("POST", "/api/saved", {
            "id": "article-1", "title": "En positiv nyhet", "excerpt": "Kort text",
            "source": "Testkälla", "url": "https://example.com/news", "image": "/news-images/ai/progress.webp"
        }, cookie)
        self.assertEqual(status, 201)
        status, data, _ = self.request("GET", "/api/saved", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(data["articles"][0]["article_id"], "article-1")
        self.assertEqual(data["articles"][0]["image"], "/news-images/ai/progress.webp")

        status, topic_data, _ = self.request("POST", "/api/forum/topics", {
            "title": "Ett nytt gott initiativ", "category": "Lokalt",
            "body": "Det här är ett tillräckligt långt foruminlägg."
        }, cookie)
        self.assertEqual(status, 202)
        topic_id = topic_data["topicId"]
        status, own, _ = self.request("GET", "/api/forum/topics", cookie=cookie)
        status, public, _ = self.request("GET", "/api/forum/topics")
        self.assertEqual(len(own["topics"]), 1)
        self.assertEqual(len(public["topics"]), 0)

        status, index, _ = self.request("GET", "/api/forum/index")
        self.assertEqual(status, 200)
        self.assertEqual(len(index["groups"]), 3)
        self.assertEqual(sum(len(group["sections"]) for group in index["groups"]), 10)

        status, section, _ = self.request("GET", "/api/forum/topics?section=lokalt-engagemang", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(section["topics"][0]["id"], topic_id)
        self.assertEqual(section["topics"][0]["status"], "pending")

        with server.db_connect() as db:
            db.execute("UPDATE forum_topics SET status='published' WHERE id=?", (topic_id,))
        status, followed, _ = self.request("POST", "/api/forum/follow", {"topicId": topic_id}, cookie)
        self.assertEqual(status, 201)
        self.assertTrue(followed["followed"])
        status, detail, _ = self.request("GET", f"/api/forum/topic?id={topic_id}", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(detail["section"]["id"], "lokalt-engagemang")
        self.assertTrue(detail["topic"]["followed"])
        status, unfollowed, _ = self.request("DELETE", f"/api/forum/follow/{topic_id}", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertFalse(unfollowed["followed"])

    def test_spoofed_cloudflare_ip_is_ignored_without_trusted_proxy(self):
        previous = os.environ.pop("GLIMT_TRUST_PROXY", None)
        server._rate_state.clear()
        try:
            first, _, _ = self.request("POST", "/api/auth/login", {
                "email": "missing@example.com", "password": "wrong-password"
            }, extra_headers={"CF-Connecting-IP": "198.51.100.10"})
            second, _, _ = self.request("POST", "/api/auth/login", {
                "email": "missing@example.com", "password": "wrong-password"
            }, extra_headers={"CF-Connecting-IP": "198.51.100.11"})
        finally:
            if previous is not None:
                os.environ["GLIMT_TRUST_PROXY"] = previous
        self.assertEqual(first, 401)
        self.assertEqual(second, 429)

    def test_google_login_does_not_auto_link_a_password_account(self):
        with server.db_connect() as db:
            db.execute(
                "INSERT INTO users(id,email,name,password_hash,created_at) VALUES (?,?,?,?,?)",
                ("password-user", "linked@example.com", "Lokal användare", server.hash_password("password-123"), server.iso_now()),
            )
        original = server.google_identity
        server.google_identity = lambda _credential: {
            "sub": "google-sub", "email": "linked@example.com", "email_verified": True,
            "aud": "client", "exp": int(server.time.time()) + 300,
        }
        server._rate_state.clear()
        try:
            status, data, _ = self.request("POST", "/api/auth/google", {"credential": "signed-token"})
        finally:
            server.google_identity = original
        self.assertEqual(status, 409)
        self.assertIn("lösenord", data["error"])
        with server.db_connect() as db:
            row = db.execute("SELECT google_sub FROM users WHERE id='password-user'").fetchone()
        self.assertIsNone(row["google_sub"])

    def test_corrupt_news_json_returns_service_unavailable(self):
        original = server.NEWS_FILE
        broken = Path(self.temp.name) / "broken-news.json"
        broken.write_text("{not valid json", encoding="utf-8")
        server.NEWS_FILE = broken
        try:
            status, data, _ = self.request("GET", "/api/news")
        finally:
            server.NEWS_FILE = original
        self.assertEqual(status, 503)
        self.assertIn("otillgänglig", data["error"])

    def test_newsletter_endpoint_is_explicitly_a_non_persisting_demo(self):
        invalid, _, _ = self.request("POST", "/api/newsletter", {"email": "inte-en-adress"})
        valid, data, _ = self.request("POST", "/api/newsletter", {"email": "test@example.com"})
        self.assertEqual(invalid, 400)
        self.assertEqual(valid, 200)
        self.assertIn("sparades inte", data["message"])


class PasswordTests(unittest.TestCase):
    def test_saved_images_only_accept_local_ai_assets(self):
        self.assertEqual(server.safe_saved_image("/news-images/ai/nature.webp"), "/news-images/ai/nature.webp")
        article_image = "/news-images/ai/articles/0123456789abcdefabcd-aabbccdd-v1.webp"
        self.assertEqual(server.safe_saved_image(article_image), article_image)
        self.assertEqual(server.safe_saved_image(article_image.replace("-v1.webp", "-v2.webp")), "")
        self.assertEqual(server.safe_saved_image("https://tracker.example/image.jpg"), "")
        self.assertEqual(server.safe_saved_image("/news-images/ai/../../server.py"), "")
        self.assertEqual(server.safe_saved_image("/news-images/ai/articles/../../server.py.webp"), "")

    def test_scrypt_password_roundtrip(self):
        encoded = server.hash_password("ett långt lösenord")
        self.assertTrue(server.verify_password("ett långt lösenord", encoded))
        self.assertFalse(server.verify_password("fel", encoded))

    def test_google_claims_require_verified_email(self):
        profile = {"sub": "google-user", "email": "person@example.com", "email_verified": False,
                   "aud": "client-id", "exp": int(server.time.time()) + 300}
        with self.assertRaisesRegex(ValueError, "verifieras"):
            server.validate_google_profile(profile, "client-id")


if __name__ == "__main__":
    unittest.main()
