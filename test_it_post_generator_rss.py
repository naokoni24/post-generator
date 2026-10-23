import io
import json
import unittest
from unittest.mock import patch

import it_post_generator_rss as app
from it_post_generator_rss import (
    Handler,
    MAX_JSON_BODY_BYTES,
    call_gemini,
    fetch_rss,
    validate_external_http_url,
)


class JsonPayloadTests(unittest.TestCase):
    def make_handler(self, body=b"", content_length=None):
        handler = Handler.__new__(Handler)
        handler.headers = {}
        if content_length is not None:
            handler.headers["Content-Length"] = str(content_length)
        handler.rfile = io.BytesIO(body)
        responses = []
        handler.send_json = lambda status, payload: responses.append((status, payload))
        return handler, responses

    def test_reads_json_object(self):
        body = json.dumps({"messages": []}).encode()
        handler, responses = self.make_handler(body, len(body))

        self.assertEqual({"messages": []}, handler._read_json_payload())
        self.assertEqual([], responses)

    def test_rejects_malformed_json(self):
        handler, responses = self.make_handler(b"{bad", 4)

        self.assertIsNone(handler._read_json_payload())
        self.assertEqual(400, responses[0][0])

    def test_rejects_non_object_json(self):
        handler, responses = self.make_handler(b"[]", 2)

        self.assertIsNone(handler._read_json_payload())
        self.assertEqual(400, responses[0][0])

    def test_requires_content_length(self):
        handler, responses = self.make_handler(b"{}")

        self.assertIsNone(handler._read_json_payload())
        self.assertEqual(411, responses[0][0])

    def test_rejects_oversized_body_before_reading(self):
        handler, responses = self.make_handler(b"{}", MAX_JSON_BODY_BYTES + 1)

        self.assertIsNone(handler._read_json_payload())
        self.assertEqual(413, responses[0][0])
        self.assertEqual(0, handler.rfile.tell())

    def test_rejects_negative_content_length(self):
        handler, responses = self.make_handler(b"{}", -1)

        self.assertIsNone(handler._read_json_payload())
        self.assertEqual(400, responses[0][0])


class ExternalUrlTests(unittest.TestCase):
    def test_accepts_public_https_url_without_resolution(self):
        url = "https://example.com/article"
        self.assertEqual(url, validate_external_http_url(url, resolve_host=False))

    def test_rejects_non_http_and_local_urls(self):
        invalid_urls = (
            "file:///etc/passwd",
            "http://localhost/admin",
            "http://127.0.0.1/private",
            "http://[::1]/private",
            "https://user:password@example.com/article",
        )
        for url in invalid_urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_external_http_url(url, resolve_host=False)


class _FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.body if size < 0 else self.body[:size]


class FeedParsingTests(unittest.TestCase):
    def setUp(self):
        app._RSS_CACHE.clear()
        app._RSS_FAIL_CACHE.clear()

    def test_resolves_relative_rss_article_url(self):
        xml = b"""<?xml version="1.0"?>
        <rss><channel><item>
          <title>Test article</title><link>/posts/1</link>
          <pubDate>Tue, 28 Jul 2026 00:00:00 GMT</pubDate>
        </item></channel></rss>"""
        fake_opener = unittest.mock.Mock()
        fake_opener.open.return_value = _FakeResponse(xml)
        with patch("urllib.request.build_opener", return_value=fake_opener):
            articles = fetch_rss("https://example.com/feed.xml", "Example")

        self.assertEqual("https://example.com/posts/1", articles[0]["url"])

    def test_skips_rss_item_without_link(self):
        xml = b"""<?xml version="1.0"?>
        <rss><channel><item><title>No link</title></item></channel></rss>"""
        fake_opener = unittest.mock.Mock()
        fake_opener.open.return_value = _FakeResponse(xml)
        with patch("urllib.request.build_opener", return_value=fake_opener):
            articles = fetch_rss("https://example.com/feed.xml", "Example")

        self.assertEqual([], articles)


class GeminiRequestTests(unittest.TestCase):
    def test_api_key_is_sent_in_header_not_url(self):
        response = _FakeResponse(json.dumps({
            "candidates": [{"content": {"parts": [{"text": "ok"}]}}]
        }).encode())
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            return response

        with patch.object(app, "API_KEY", "secret-key"), patch.object(app, "urlopen", fake_urlopen):
            self.assertEqual("ok", call_gemini("hello", max_retries=1))

        request = captured["request"]
        self.assertNotIn("secret-key", request.full_url)
        self.assertEqual("secret-key", request.get_header("X-goog-api-key"))


if __name__ == "__main__":
    unittest.main()
