"""환경 변수와 프로젝트 경로를 한곳에서 관리한다."""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs) -> bool:
        """python-dotenv 설치 전에는 운영체제 환경 변수만 사용한다."""
        return False


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
OUTPUT_DIR = DATA_DIR / "output"
DATABASE_PATH = DATA_DIR / "public_brief.db"

load_dotenv(BASE_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
MOHW_RSS_URL = (
    "https://www.mohw.go.kr/rss/board.es"
    "?mid=a10503000000&bid=0027&info"
)
HTTP_TIMEOUT_SECONDS = 20
MAX_RETRIES = 1
