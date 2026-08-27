"""Public Brief CLI 애플리케이션의 시작점."""

from cli import run


def main() -> int:
    """CLI 인자를 읽고 선택된 명령을 실행한다."""
    return run()


if __name__ == "__main__":
    raise SystemExit(main())

