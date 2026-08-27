"""Public Brief의 argparse 기반 명령줄 인터페이스."""

import argparse
import logging
from collections.abc import Sequence

from collectors.rss_collector import fetch_rss, parse_iso_date
from processors.cleaner import clean_raw_directory
from storage.raw_storage import save_raw_fetch_result


CATEGORIES = ("고용", "청년", "복지", "교육", "AI", "산업", "디지털", "기타")
PRIORITIES = ("HIGH", "MEDIUM", "LOW")
EXPORT_FORMATS = ("csv", "xlsx")


def positive_int(value: str) -> int:
    """CLI 입력값이 1 이상의 정수인지 검사한다."""
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("1 이상의 정수를 입력하세요.")
    return number


def add_date_options(parser: argparse.ArgumentParser) -> None:
    """기간 필터 옵션을 명령에 추가한다."""
    parser.add_argument(
        "--date-from",
        metavar="YYYY-MM-DD",
        help="조회 시작일",
    )
    parser.add_argument(
        "--date-to",
        metavar="YYYY-MM-DD",
        help="조회 종료일",
    )


def add_filter_options(parser: argparse.ArgumentParser) -> None:
    """분야와 중요도 필터 옵션을 명령에 추가한다."""
    parser.add_argument(
        "--category",
        choices=CATEGORIES,
        help="선택한 업무 분야만 처리",
    )
    parser.add_argument(
        "--priority",
        choices=PRIORITIES,
        help="선택한 중요도만 처리",
    )


def add_limit_option(parser: argparse.ArgumentParser) -> None:
    """처리 건수 제한 옵션을 명령에 추가한다."""
    parser.add_argument(
        "--limit",
        type=positive_int,
        default=20,
        help="처리할 최대 자료 수 (기본값: 20)",
    )


def build_parser() -> argparse.ArgumentParser:
    """최상위 파서와 일곱 개의 서브커맨드를 만든다."""
    parser = argparse.ArgumentParser(
        prog="public-brief",
        description="공공정보를 수집·분석하여 업무 브리핑을 만드는 CLI",
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        title="명령",
    )

    fetch_parser = subparsers.add_parser(
        "fetch",
        help="보건복지부 RSS에서 새 자료 수집",
        description="보건복지부 RSS에서 원본 자료를 수집합니다.",
    )
    add_limit_option(fetch_parser)
    add_date_options(fetch_parser)
    fetch_parser.set_defaults(handler=handle_fetch)

    clean_parser = subparsers.add_parser(
        "clean",
        help="원본 자료 정제 및 중복 제거",
        description="저장된 원본 자료를 정제하고 중복을 제거합니다.",
    )
    add_limit_option(clean_parser)
    clean_parser.set_defaults(handler=handle_clean)

    summarize_parser = subparsers.add_parser(
        "summarize",
        help="Gemini로 자료 요약",
        description="정제된 자료를 Gemini API로 요약합니다.",
    )
    add_limit_option(summarize_parser)
    summarize_parser.add_argument(
        "--unsummarized",
        action="store_true",
        help="아직 요약되지 않은 자료만 처리",
    )
    summarize_parser.set_defaults(handler=handle_summarize)

    classify_parser = subparsers.add_parser(
        "classify",
        help="자료의 분야와 중요도 분류",
        description="자료를 업무 분야와 중요도로 분류합니다.",
    )
    add_limit_option(classify_parser)
    classify_parser.set_defaults(handler=handle_classify)

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="기간별 트렌드 분석",
        description="저장된 자료의 분야·키워드·중요도 분포를 분석합니다.",
    )
    add_date_options(analyze_parser)
    add_filter_options(analyze_parser)
    analyze_parser.set_defaults(handler=handle_analyze)

    report_parser = subparsers.add_parser(
        "report",
        help="Markdown 업무 브리핑 생성",
        description="분석 결과를 Markdown 업무 브리핑으로 만듭니다.",
    )
    add_date_options(report_parser)
    add_filter_options(report_parser)
    report_parser.set_defaults(handler=handle_report)

    export_parser = subparsers.add_parser(
        "export",
        help="CSV 또는 Excel 파일로 내보내기",
        description="정제·분석 데이터를 표 파일로 내보냅니다.",
    )
    export_parser.add_argument(
        "--format",
        choices=EXPORT_FORMATS,
        default="xlsx",
        help="내보낼 파일 형식 (기본값: xlsx)",
    )
    add_date_options(export_parser)
    add_filter_options(export_parser)
    export_parser.set_defaults(handler=handle_export)

    return parser


def selected_options(args: argparse.Namespace) -> str:
    """사용자가 지정한 옵션을 확인용 문자열로 만든다."""
    excluded = {"command", "handler"}
    options = [
        f"{key}={value}"
        for key, value in vars(args).items()
        if key not in excluded and value is not None and value is not False
    ]
    return ", ".join(options) if options else "없음"


def pending_message(args: argparse.Namespace, description: str) -> int:
    """후속 단계에서 채울 기능임을 명확히 안내한다."""
    print(f"[INFO] {description}")
    print(f"[INFO] 선택 옵션: {selected_options(args)}")
    print("[INFO] 명령 구조가 준비되었습니다. 실제 처리 기능은 다음 구현 단계에서 연결됩니다.")
    return 0


def handle_fetch(args: argparse.Namespace) -> int:
    try:
        date_from = parse_iso_date(args.date_from)
        date_to = parse_iso_date(args.date_to)
    except ValueError:
        print("[ERROR] 날짜는 YYYY-MM-DD 형식으로 입력하세요.")
        return 2

    if date_from is not None and date_to is not None and date_from > date_to:
        print("[ERROR] --date-from은 --date-to보다 늦을 수 없습니다.")
        return 2

    print("[INFO] 공공정보 수집 시작")
    print("[INFO] source=보건복지부 보도자료 RSS")
    result = fetch_rss(
        limit=args.limit,
        date_from=date_from,
        date_to=date_to,
    )

    if result.errors and not result.items:
        print(f"[ERROR] RSS 수집 실패: {result.errors[-1]}")
        print(f"[INFO] 요청 횟수: {result.attempts}회")
        return 1

    successful_count = len(result.successful_items)
    failed_count = len(result.failed_items)
    if successful_count == 0:
        print("[WARNING] 수집된 데이터가 없습니다.")
    else:
        print(f"[INFO] 총 {successful_count}건 수집")
    if failed_count:
        print(f"[WARNING] 항목 수집 실패: {failed_count}건")
    print(f"[INFO] 수집 시각: {result.collected_at}")
    try:
        raw_path = save_raw_fetch_result(result)
    except OSError as error:
        print(f"[ERROR] Raw 데이터 저장 실패: {error}")
        return 1
    print(f"[INFO] Raw 데이터 저장 완료: {raw_path}")
    return 0


def handle_clean(args: argparse.Namespace) -> int:
    print("[INFO] 데이터 정제 시작")
    try:
        result = clean_raw_directory(limit=args.limit)
    except OSError as error:
        print(f"[ERROR] 데이터 정제 실패: {error}")
        return 1

    if result.raw_files == 0:
        print("[WARNING] 정제할 Raw JSON 파일이 없습니다.")
        return 0
    if result.total_items == 0:
        print("[WARNING] 정제할 데이터가 없습니다.")
        return 0

    print(f"[INFO] 정제 대상: {result.total_items}건")
    print(f"[INFO] 신규 저장: {result.inserted}건")
    if result.duplicates:
        print(f"[WARNING] 중복 데이터 스킵: {result.duplicates}건")
    if result.excluded:
        print(f"[WARNING] 검증 실패 제외: {result.excluded}건")
    if result.empty_content:
        print(f"[WARNING] 본문 없음: {result.empty_content}건")
    print("[INFO] SQLite 저장 완료")
    return 0


def handle_summarize(args: argparse.Namespace) -> int:
    return pending_message(args, "Gemini 요약 명령")


def handle_classify(args: argparse.Namespace) -> int:
    return pending_message(args, "분야 및 중요도 분류 명령")


def handle_analyze(args: argparse.Namespace) -> int:
    return pending_message(args, "트렌드 분석 명령")


def handle_report(args: argparse.Namespace) -> int:
    return pending_message(args, "Markdown 브리핑 생성 명령")


def handle_export(args: argparse.Namespace) -> int:
    return pending_message(args, "표 파일 내보내기 명령")


def run(argv: Sequence[str] | None = None) -> int:
    """인자를 해석하고 선택한 명령 처리기를 실행한다."""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s",
    )
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)
