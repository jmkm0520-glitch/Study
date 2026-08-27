"""보건복지부 보도자료 RSS를 안전하게 수집한다."""

from __future__ import annotations

import logging
import socket
import ssl
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import HTTP_TIMEOUT_SECONDS, MAX_RETRIES, MOHW_RSS_URL


LOGGER = logging.getLogger(__name__)
SOURCE_NAME = "보건복지부"
USER_AGENT = "PublicBrief/1.0 (+portfolio-project)"


@dataclass(slots=True)
class CollectedItem:
    """RSS 항목 하나의 수집 결과."""

    title: str
    source: str
    published_at: str
    content: str
    url: str
    collected_at: str
    category: str | None = None
    success: bool = True
    error: str | None = None


@dataclass(slots=True)
class FetchResult:
    """한 번의 RSS 수집 실행 결과."""

    source: str
    source_url: str
    collected_at: str
    attempts: int = 0
    items: list[CollectedItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def successful_items(self) -> list[CollectedItem]:
        return [item for item in self.items if item.success]

    @property
    def failed_items(self) -> list[CollectedItem]:
        return [item for item in self.items if not item.success]


def utc_now_iso() -> str:
    """UTC 수집 시각을 초 단위 ISO 8601 문자열로 반환한다."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso_date(value: str | None) -> date | None:
    """CLI의 YYYY-MM-DD 값을 날짜로 변환한다."""
    if value is None:
        return None
    return date.fromisoformat(value)


def parse_rss_date(value: str) -> datetime | None:
    """RSS의 RFC 2822 날짜를 timezone이 포함된 datetime으로 변환한다."""
    if not value.strip():
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def in_date_range(
    published_at: str,
    date_from: date | None,
    date_to: date | None,
) -> bool:
    """작성일이 사용자가 선택한 기간에 포함되는지 확인한다."""
    if date_from is None and date_to is None:
        return True
    parsed = parse_rss_date(published_at)
    if parsed is None:
        return False
    published_date = parsed.date()
    if date_from is not None and published_date < date_from:
        return False
    if date_to is not None and published_date > date_to:
        return False
    return True


def text_of(element: ET.Element, tag: str) -> str:
    """자식 XML 태그의 텍스트를 안전하게 읽는다."""
    child = element.find(tag)
    if child is None or child.text is None:
        return ""
    return unescape(child.text).strip()


def parse_item(element: ET.Element, collected_at: str) -> CollectedItem:
    """XML item 하나를 공통 수집 필드로 변환한다."""
    title = text_of(element, "title")
    url = text_of(element, "link")
    published_at = text_of(element, "pubDate")
    content = text_of(element, "description")
    category = text_of(element, "category") or None

    missing = [
        field_name
        for field_name, value in (("title", title), ("url", url))
        if not value
    ]
    if missing:
        return CollectedItem(
            title=title,
            source=SOURCE_NAME,
            published_at=published_at,
            content=content,
            url=url,
            collected_at=collected_at,
            category=category,
            success=False,
            error=f"필수 필드 누락: {', '.join(missing)}",
        )

    return CollectedItem(
        title=title,
        source=SOURCE_NAME,
        published_at=published_at,
        content=content,
        url=url,
        collected_at=collected_at,
        category=category,
    )


def parse_rss(
    xml_data: bytes,
    *,
    collected_at: str,
    limit: int,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[CollectedItem]:
    """RSS XML을 파싱하고 기간과 최대 건수를 적용한다."""
    root = ET.fromstring(xml_data)
    parsed_items: list[CollectedItem] = []

    for element in root.findall("./channel/item"):
        item = parse_item(element, collected_at)
        if item.success and not in_date_range(item.published_at, date_from, date_to):
            continue
        parsed_items.append(item)
        if len(parsed_items) >= limit:
            break

    return parsed_items


def default_opener(request: Request, timeout: int):
    """테스트에서 교체할 수 있는 기본 HTTP 요청 함수."""
    verify_paths = ssl.get_default_verify_paths()
    system_ca_file = "/etc/ssl/cert.pem"
    if verify_paths.cafile is None and Path(system_ca_file).is_file():
        context = ssl.create_default_context(cafile=system_ca_file)
    else:
        context = ssl.create_default_context()
    return urlopen(request, timeout=timeout, context=context)


def fetch_rss(
    *,
    limit: int = 20,
    date_from: date | None = None,
    date_to: date | None = None,
    url: str = MOHW_RSS_URL,
    timeout: int = HTTP_TIMEOUT_SECONDS,
    max_retries: int = MAX_RETRIES,
    opener: Callable = default_opener,
) -> FetchResult:
    """RSS를 요청하고 최대 한 번 재시도한 뒤 항목별 결과를 반환한다."""
    collected_at = utc_now_iso()
    result = FetchResult(
        source=SOURCE_NAME,
        source_url=url,
        collected_at=collected_at,
    )
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml",
        },
    )

    for attempt in range(max_retries + 1):
        result.attempts = attempt + 1
        try:
            LOGGER.info("RSS 요청 시작: source=%s attempt=%s", SOURCE_NAME, attempt + 1)
            with opener(request, timeout) as response:
                xml_data = response.read()
            result.items = parse_rss(
                xml_data,
                collected_at=collected_at,
                limit=limit,
                date_from=date_from,
                date_to=date_to,
            )
            for index, item in enumerate(result.failed_items, start=1):
                LOGGER.warning("RSS 항목 수집 실패: index=%s reason=%s", index, item.error)
            return result
        except (HTTPError, URLError, TimeoutError, socket.timeout) as error:
            message = f"네트워크 오류: {error}"
        except ET.ParseError as error:
            message = f"RSS XML 파싱 오류: {error}"

        result.errors.append(message)
        if attempt < max_retries:
            LOGGER.warning("%s, 재시도합니다.", message)
        else:
            LOGGER.error("%s, 수집을 종료합니다.", message)

    return result
