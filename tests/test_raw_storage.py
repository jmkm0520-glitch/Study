"""Raw 데이터 저장 기능 테스트."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collectors.rss_collector import CollectedItem, FetchResult
from storage.raw_storage import save_raw_fetch_result


def sample_result() -> FetchResult:
    result = FetchResult(
        source="보건복지부",
        source_url="https://example.go.kr/rss",
        collected_at="2026-08-27T00:00:00+00:00",
        attempts=1,
    )
    result.items.append(
        CollectedItem(
            title="테스트 보도자료",
            source="보건복지부",
            published_at="Wed, 26 Aug 2026 09:07:00 GMT",
            url="https://example.go.kr/1",
            content="테스트 본문",
            collected_at="2026-08-27T00:00:00+00:00",
        )
    )
    return result


class RawStorageTest(unittest.TestCase):
    def test_saves_required_fields_as_utf8_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = save_raw_fetch_result(sample_result(), Path(directory))
            payload = json.loads(path.read_text(encoding="utf-8"))
            item = payload["items"][0]

            required = {
                "title",
                "source",
                "published_at",
                "url",
                "content",
                "collected_at",
            }
            self.assertTrue(required.issubset(item))
            self.assertEqual("테스트 보도자료", item["title"])
            self.assertEqual("테스트 본문", item["content"])

    def test_each_save_creates_a_new_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            raw_dir = Path(directory)
            first = save_raw_fetch_result(sample_result(), raw_dir)
            first_content = first.read_bytes()
            second = save_raw_fetch_result(sample_result(), raw_dir)

            self.assertNotEqual(first, second)
            self.assertEqual(2, len(list(raw_dir.glob("*.json"))))
            self.assertEqual(first_content, first.read_bytes())

    def test_existing_file_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            raw_dir = Path(directory)
            existing = raw_dir / "fixed.json"
            existing.write_text("original", encoding="utf-8")

            with patch(
                "storage.raw_storage.build_raw_filename",
                return_value="fixed.json",
            ):
                with self.assertRaises(FileExistsError):
                    save_raw_fetch_result(sample_result(), raw_dir)

            self.assertEqual("original", existing.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

