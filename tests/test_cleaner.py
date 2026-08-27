"""데이터 정제와 SQLite 영구 저장 테스트."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from processors.cleaner import clean_item, clean_raw_directory
from storage.database import count_documents


class CleanerUnitTest(unittest.TestCase):
    def test_cleans_html_whitespace_date_and_url(self) -> None:
        document, error = clean_item(
            {
                "title": "  복지\t정책  ",
                "source": "보건복지부",
                "published_at": "Wed, 26 Aug 2026 09:07:00 GMT",
                "url": "HTTPS://Example.GO.KR/item?id=1#section",
                "content": "<p>지원&nbsp; 내용</p>\n<div>확인</div>",
                "collected_at": "2026-08-27T00:00:00+00:00",
                "category": None,
            }
        )
        self.assertIsNone(error)
        self.assertEqual("복지 정책", document["title"])
        self.assertEqual("지원 내용 확인", document["content"])
        self.assertEqual("2026-08-26T09:07:00+00:00", document["published_at"])
        self.assertEqual("https://example.go.kr/item?id=1", document["url"])

    def test_missing_title_is_excluded(self) -> None:
        document, error = clean_item(
            {
                "title": " ",
                "url": "https://example.go.kr/1",
                "collected_at": "now",
            }
        )
        self.assertIsNone(document)
        self.assertIn("제목", error)

    def test_missing_or_invalid_url_is_excluded(self) -> None:
        for url in ("", None, "not-a-url", "ftp://example.go.kr/file"):
            with self.subTest(url=url):
                document, error = clean_item(
                    {"title": "제목", "url": url, "collected_at": "now"}
                )
                self.assertIsNone(document)
                self.assertIn("URL", error)

    def test_empty_content_is_marked(self) -> None:
        document, error = clean_item(
            {
                "title": "제목",
                "url": "https://example.go.kr/1",
                "content": "<p> </p>",
                "collected_at": "now",
            }
        )
        self.assertIsNone(error)
        self.assertEqual("", document["content"])
        self.assertTrue(document["content_missing"])

    def test_invalid_unicode_is_replaced_safely(self) -> None:
        document, error = clean_item(
            {
                "title": "깨진\udcff제목",
                "url": "https://example.go.kr/1",
                "content": "본문",
                "collected_at": "now",
            }
        )
        self.assertIsNone(error)
        document["title"].encode("utf-8")


class CleanerIntegrationTest(unittest.TestCase):
    def write_raw(self, raw_dir: Path, items: list) -> None:
        payload = {"items": items}
        (raw_dir / "sample.json").write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_saves_to_sqlite_and_skips_duplicate_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_dir = root / "raw"
            raw_dir.mkdir()
            db_path = root / "public_brief.db"
            base = {
                "source": "보건복지부",
                "published_at": "Wed, 26 Aug 2026 09:07:00 GMT",
                "content": "본문",
                "collected_at": "2026-08-27T00:00:00+00:00",
            }
            self.write_raw(
                raw_dir,
                [
                    {**base, "title": "첫 번째", "url": "https://example.go.kr/1"},
                    {**base, "title": "중복", "url": "https://example.go.kr/1"},
                    {**base, "title": "두 번째", "url": "https://example.go.kr/2"},
                ],
            )

            first = clean_raw_directory(raw_dir=raw_dir, db_path=db_path)
            second = clean_raw_directory(raw_dir=raw_dir, db_path=db_path)

            self.assertEqual(2, first.inserted)
            self.assertEqual(1, first.duplicates)
            self.assertEqual(0, second.inserted)
            self.assertEqual(3, second.duplicates)
            self.assertEqual(2, count_documents(db_path))

            with sqlite3.connect(db_path) as connection:
                rows = connection.execute(
                    "SELECT title, status FROM documents ORDER BY url"
                ).fetchall()
            self.assertEqual([("첫 번째", "CLEANED"), ("두 번째", "CLEANED")], rows)

    def test_raw_file_is_not_modified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_dir = root / "raw"
            raw_dir.mkdir()
            db_path = root / "public_brief.db"
            self.write_raw(
                raw_dir,
                [
                    {
                        "title": "제목",
                        "source": "보건복지부",
                        "published_at": "Wed, 26 Aug 2026 09:07:00 GMT",
                        "url": "https://example.go.kr/1",
                        "content": "<p>본문</p>",
                        "collected_at": "now",
                    }
                ],
            )
            raw_path = raw_dir / "sample.json"
            before = raw_path.read_bytes()
            clean_raw_directory(raw_dir=raw_dir, db_path=db_path)
            self.assertEqual(before, raw_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
