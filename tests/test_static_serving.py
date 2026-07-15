import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

import server


class StaticServingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.original_dist = server.DIST_DIR
        server.DIST_DIR = Path(cls.temp.name) / "dist"
        (server.DIST_DIR / "assets").mkdir(parents=True)
        (server.DIST_DIR / "index.html").write_text("<!doctype html><title>Vite shell</title>", encoding="utf-8")
        (server.DIST_DIR / "assets/app-123.js").write_text("console.log('vite');", encoding="utf-8")
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        server.DIST_DIR = cls.original_dist
        cls.temp.cleanup()

    def request(self, path):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        connection.request("GET", path)
        response = connection.getresponse()
        body = response.read()
        result = response.status, response.getheaders(), body
        connection.close()
        return result

    def test_vite_index_and_spa_routes(self):
        for path in ("/", "/nyheter/veckans-ljusglimt", "/forum?section=lokalt", "/forum.html?section=lokalt"):
            status, headers, body = self.request(path)
            self.assertEqual(status, 200, path)
            self.assertIn(b"Vite shell", body)
            self.assertIn("text/html", dict(headers)["Content-Type"])
            self.assertIn("default-src 'self'", dict(headers)["Content-Security-Policy"])

    def test_vite_asset_has_content_type_and_long_cache(self):
        status, headers, body = self.request("/assets/app-123.js")
        headers = dict(headers)
        self.assertEqual(status, 200)
        self.assertEqual(body, b"console.log('vite');")
        self.assertIn("javascript", headers["Content-Type"])
        self.assertIn("immutable", headers["Cache-Control"])

    def test_missing_asset_does_not_fall_back_to_spa(self):
        status, _, body = self.request("/assets/missing.js")
        self.assertEqual(status, 404)
        self.assertNotIn(b"Vite shell", body)

    def test_traversal_is_rejected(self):
        status, _, body = self.request("/%2e%2e/server.py")
        self.assertEqual(status, 403)
        self.assertNotIn(b"Ljusglimt: webbserver", body)

    def test_unknown_api_stays_json_404(self):
        status, headers, body = self.request("/api/does-not-exist")
        self.assertEqual(status, 404)
        self.assertIn("application/json", dict(headers)["Content-Type"])
        self.assertIn("error", json.loads(body.decode("utf-8")))

    def test_public_news_data_remains_available(self):
        status, headers, body = self.request("/data/seed-news.json")
        self.assertEqual(status, 200)
        self.assertIn("application/json", dict(headers)["Content-Type"])
        self.assertIn("articles", json.loads(body.decode("utf-8")))

    def test_legacy_pages_remain_available_without_dist(self):
        dist = server.DIST_DIR
        server.DIST_DIR = Path(self.temp.name) / "not-built"
        try:
            status, headers, body = self.request("/forum.html?section=lokalt-engagemang")
        finally:
            server.DIST_DIR = dist
        self.assertEqual(status, 200)
        self.assertIn("text/html", dict(headers)["Content-Type"])
        self.assertIn(b"<!doctype html>", body.lower())


if __name__ == "__main__":
    unittest.main()
