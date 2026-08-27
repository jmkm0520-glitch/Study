"""RSS 수집 기능 테스트."""

import socket
import unittest
from datetime import date

from collectors.rss_collector import fetch_rss, parse_rss


SAMPLE_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test feed</title>
    <item>
      <title><![CDATA[AI policy update]]></title>
      <link>https://example.go.kr/1</link>
      <description><![CDATA[Policy &amp; support details]]></description>
      <pubDate>Wed, 26 Aug 2026 09:07:00 GMT</pubDate>
      <author>Tester</author>
    </item>
    <item>
      <title>Second item</title>
      <link>https://example.go.kr/2</link>
      <description>Second content</description>
      <pubDate>Tue, 25 Aug 2026 09:07:00 GMT</pubDate>
      <category>Welfare</category>
    </item>
  </channel>
</rss>
"""


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self) -> bytes:
        return self.body


class RssParserTest(unittest.TestCase):
    def test_collects_required_fields(self) -> None:
        items = parse_rss(
            SAMPLE_RSS,
            collected_at="2026-08-27T00:00:00+00:00",
            limit=20,
        )
        self.assertEqual(2, len(items))
        first = items[0]
        self.assertEqual("AI policy update", first.title)
        self.assertEqual("보건복지부", first.source)
        self.assertEqual("Wed, 26 Aug 2026 09:07:00 GMT", first.published_at)
        self.assertEqual("Policy & support details", first.content)
        self.assertEqual("https://example.go.kr/1", first.url)
        self.assertEqual("2026-08-27T00:00:00+00:00", first.collected_at)
        self.assertTrue(first.success)

    def test_limit_and_date_range(self) -> None:
        items = parse_rss(
            SAMPLE_RSS,
            collected_at="2026-08-27T00:00:00+00:00",
            limit=1,
            date_from=date(2026, 8, 26),
            date_to=date(2026, 8, 26),
        )
        self.assertEqual(1, len(items))
        self.assertEqual("AI policy update", items[0].title)

    def test_missing_required_field_is_item_failure(self) -> None:
        xml = b"""<rss><channel>
          <item><link>https://example.go.kr/missing-title</link></item>
          <item><title>Valid</title><link>https://example.go.kr/valid</link></item>
        </channel></rss>"""
        items = parse_rss(xml, collected_at="now", limit=20)
        self.assertEqual(2, len(items))
        self.assertFalse(items[0].success)
        self.assertIn("title", items[0].error)
        self.assertTrue(items[1].success)

    def test_empty_feed_returns_empty_list(self) -> None:
        items = parse_rss(
            b"<rss><channel></channel></rss>",
            collected_at="now",
            limit=20,
        )
        self.assertEqual([], items)


class RssRequestTest(unittest.TestCase):
    def test_fetch_uses_timeout_and_parses_response(self) -> None:
        calls = []

        def opener(request, timeout):
            calls.append((request.full_url, timeout))
            return FakeResponse(SAMPLE_RSS)

        result = fetch_rss(limit=1, timeout=7, max_retries=1, opener=opener)
        self.assertEqual(1, len(result.successful_items))
        self.assertEqual([("https://www.mohw.go.kr/rss/board.es?mid=a10503000000&bid=0027&info", 7)], calls)

    def test_network_timeout_retries_once(self) -> None:
        calls = []

        def opener(request, timeout):
            calls.append(timeout)
            raise socket.timeout("timed out")

        result = fetch_rss(timeout=3, max_retries=1, opener=opener)
        self.assertEqual([3, 3], calls)
        self.assertEqual(2, result.attempts)
        self.assertEqual(2, len(result.errors))
        self.assertEqual([], result.items)


if __name__ == "__main__":
    unittest.main()

