"""SQLite 연결, 테이블 생성, 조회와 저장 기능."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from config import DATABASE_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    published_at TEXT,
    url TEXT NOT NULL UNIQUE,
    content TEXT NOT NULL DEFAULT '',
    collected_at TEXT NOT NULL,
    source_category TEXT,
    content_missing INTEGER NOT NULL DEFAULT 0 CHECK (content_missing IN (0, 1)),
    status TEXT NOT NULL DEFAULT 'CLEANED',
    summary_json TEXT,
    business_impact TEXT,
    needs_verification TEXT,
    categories_json TEXT,
    priority TEXT CHECK (priority IN ('HIGH', 'MEDIUM', 'LOW') OR priority IS NULL),
    priority_reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_documents_published_at
ON documents(published_at);

CREATE INDEX IF NOT EXISTS idx_documents_status
ON documents(status);

CREATE TABLE IF NOT EXISTS processing_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    step TEXT NOT NULL,
    item_id INTEGER,
    error_type TEXT NOT NULL,
    message TEXT NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES documents(id)
);
"""


@contextmanager
def connect(db_path: Path = DATABASE_PATH) -> Iterator[sqlite3.Connection]:
    """SQLite 연결을 열고 성공한 작업만 확정한다."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(db_path: Path = DATABASE_PATH) -> None:
    """필요한 테이블과 인덱스를 생성한다."""
    with connect(db_path) as connection:
        connection.executescript(SCHEMA)


def insert_document(connection: sqlite3.Connection, document: dict) -> bool:
    """URL이 새 값일 때만 문서를 저장하고 저장 여부를 반환한다."""
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO documents (
            title,
            source,
            published_at,
            url,
            content,
            collected_at,
            source_category,
            content_missing,
            status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'CLEANED')
        """,
        (
            document["title"],
            document["source"],
            document["published_at"],
            document["url"],
            document["content"],
            document["collected_at"],
            document.get("category"),
            int(document["content_missing"]),
        ),
    )
    return cursor.rowcount == 1


def count_documents(db_path: Path = DATABASE_PATH) -> int:
    """영구 저장된 전체 문서 수를 반환한다."""
    initialize_database(db_path)
    with connect(db_path) as connection:
        row = connection.execute("SELECT COUNT(*) AS count FROM documents").fetchone()
        return int(row["count"])
