import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

import server


class AccountApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
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
        cls.temp.cleanup()

    def request(self, method, path, payload=None, cookie=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Origin": f"http://127.0.0.1:{self.port}"}
        body = None
        if payload is not None:
            body = json.dumps(payload)
            headers["Content-Type"] = "application/json"
        if cookie:
            headers["Cookie"] = cookie
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
            "source": "Testkälla", "url": "https://example.com/news", "image": "https://example.com/image.jpg"
        }, cookie)
        self.assertEqual(status, 201)
        status, data, _ = self.request("GET", "/api/saved", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(data["articles"][0]["article_id"], "article-1")

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


class PasswordTests(unittest.TestCase):
    def test_scrypt_password_roundtrip(self):
        encoded = server.hash_password("ett långt lösenord")
        self.assertTrue(server.verify_password("ett långt lösenord", encoded))
        self.assertFalse(server.verify_password("fel", encoded))


if __name__ == "__main__":
    unittest.main()
