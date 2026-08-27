"""Raw JSON을 검증·정제하고 SQLite에 저장한다."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from collectors.rss_collector import parse_rss_date
from config import DATABASE_PATH, RAW_DATA_DIR
from storage.database import connect, initialize_database, insert_document


LOGGER = logging.getLogger(__name__)
WHITESPACE_PATTERN = re.compile(r"\s+")


class TextExtractor(HTMLParser):
    """HTML 태그를 제외하고 사람이 읽는 텍스트만 모은다."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return " ".join(self.parts)


@dataclass(slots=True)
class CleanIssue:
    """정제 중 제외 또는 주의가 필요한 항목."""

    file: str
    item_index: int | None
    issue_type: str
    message: str


@dataclass(slots=True)
class CleanResult:
    """clean 명령 한 번의 처리 결과."""

    raw_files: int = 0
    total_items: int = 0
    inserted: int = 0
    duplicates: int = 0
    excluded: int = 0
    empty_content: int = 0
    issues: list[CleanIssue] = field(default_factory=list)


def safe_utf8(value: object) -> str:
    """값을 UTF-8로 저장 가능한 NFC 문자열로 변환한다."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFC", str(value))
    return text.encode("utf-8", errors="replace").decode("utf-8")


def clean_text(value: object, *, remove_html: bool = False) -> str:
    """인코딩, HTML, 제어문자와 불필요한 공백을 정리한다."""
    text = safe_utf8(value)
    if remove_html:
        extractor = TextExtractor()
        extractor.feed(text)
        extractor.close()
        text = extractor.text()
    text = unescape(text)
    text = "".join(
        character
        for character in text
        if unicodedata.category(character) != "Cc" or character in "\n\t"
    )
    return WHITESPACE_PATTERN.sub(" ", text).strip()


def normalize_url(value: object) -> str | None:
    """HTTP(S) 원문 URL을 중복 비교에 사용할 형태로 통일한다."""
    raw_url = clean_text(value)
    if not raw_url:
        return None
    parsed = urlsplit(raw_url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            parsed.query,
            "",
        )
    )


def normalize_published_at(value: object) -> str | None:
    """RSS 작성일을 UTC ISO 8601 형식으로 통일한다."""
    raw_date = clean_text(value)
    parsed = parse_rss_date(raw_date)
    if parsed is None:
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def clean_item(item: object) -> tuple[dict | None, str | None]:
    """Raw 항목 하나를 검증·정제한다."""
    if not isinstance(item, dict):
        return None, "항목이 JSON 객체가 아닙니다."

    title = clean_text(item.get("title"))
    if not title:
        return None, "제목이 없어 제외했습니다."

    url = normalize_url(item.get("url"))
    if url is None:
        return None, "URL이 없거나 올바른 HTTP(S) 주소가 아니어서 제외했습니다."

    source = clean_text(item.get("source")) or "출처 미상"
    collected_at = clean_text(item.get("collected_at"))
    if not collected_at:
        return None, "수집 시각이 없어 제외했습니다."

    content = clean_text(item.get("content"), remove_html=True)
    published_at = normalize_published_at(item.get("published_at"))

    return (
        {
            "title": title,
            "source": source,
            "published_at": published_at,
            "url": url,
            "content": content,
            "collected_at": collected_at,
            "category": clean_text(item.get("category")) or None,
            "content_missing": not bool(content),
        },
        None,
    )


def load_raw_items(path: Path) -> list:
    """Raw JSON 파일의 items 배열을 읽는다."""
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("Raw JSON에 items 배열이 없습니다.")
    return payload["items"]


def clean_raw_directory(
    *,
    raw_dir: Path = RAW_DATA_DIR,
    db_path: Path = DATABASE_PATH,
    limit: int | None = None,
) -> CleanResult:
    """모든 Raw JSON을 읽어 정제하고 새 URL만 SQLite에 저장한다."""
    result = CleanResult()
    initialize_database(db_path)
    raw_paths = sorted(raw_dir.glob("*.json")) if raw_dir.exists() else []

    with connect(db_path) as connection:
        stop = False
        for path in raw_paths:
            if stop:
                break
            result.raw_files += 1
            try:
                items = load_raw_items(path)
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
                result.issues.append(
                    CleanIssue(path.name, None, "RAW_FILE_ERROR", str(error))
                )
                LOGGER.error("Raw 파일 읽기 실패: file=%s error=%s", path.name, error)
                continue

            for index, raw_item in enumerate(items, start=1):
                if limit is not None and result.total_items >= limit:
                    stop = True
                    break
                result.total_items += 1
                document, error = clean_item(raw_item)
                if error is not None:
                    result.excluded += 1
                    result.issues.append(
                        CleanIssue(path.name, index, "VALIDATION_ERROR", error)
                    )
                    LOGGER.warning(
                        "정제 항목 제외: file=%s index=%s reason=%s",
                        path.name,
                        index,
                        error,
                    )
                    continue

                if document["content_missing"]:
                    result.empty_content += 1
                    LOGGER.warning("본문 없음: url=%s", document["url"])

                if insert_document(connection, document):
                    result.inserted += 1
                else:
                    result.duplicates += 1
                    LOGGER.warning("중복 데이터 스킵: url=%s", document["url"])

    return result
