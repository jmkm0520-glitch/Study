"""수집 결과를 변경하지 않는 Raw JSON 파일로 보관한다."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from collectors.rss_collector import FetchResult
from config import RAW_DATA_DIR


def build_raw_filename() -> str:
    """실행마다 겹치지 않는 Raw 파일명을 만든다."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    unique_suffix = uuid4().hex[:8]
    return f"mohw_press_{timestamp}_{unique_suffix}.json"


def raw_payload(result: FetchResult) -> dict:
    """수집 결과를 JSON으로 저장 가능한 구조로 변환한다."""
    return {
        "source": result.source,
        "source_url": result.source_url,
        "collected_at": result.collected_at,
        "attempts": result.attempts,
        "errors": list(result.errors),
        "items": [asdict(item) for item in result.items],
    }


def save_raw_fetch_result(
    result: FetchResult,
    raw_dir: Path = RAW_DATA_DIR,
) -> Path:
    """기존 파일을 덮어쓰지 않고 수집 결과를 새 JSON 파일로 저장한다."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    output_path = raw_dir / build_raw_filename()
    payload = raw_payload(result)

    # x 모드는 같은 이름의 파일이 이미 있으면 실패하므로 덮어쓰지 않는다.
    with output_path.open("x", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")

    return output_path

