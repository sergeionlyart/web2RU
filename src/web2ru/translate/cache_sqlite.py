from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(slots=True)
class CacheEntry:
    translations: dict[str, str]
    status: str
    created_at: str


class TranslationCache:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS translation_cache (
                cache_key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def get(self, cache_key: str) -> CacheEntry | None:
        row = self._conn.execute(
            "SELECT payload, status, created_at FROM translation_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
        if row is None:
            return None
        payload, status, created_at = row
        return CacheEntry(
            translations=json.loads(payload),
            status=status,
            created_at=created_at,
        )

    def put(self, cache_key: str, translations: dict[str, str], status: str = "ok") -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO translation_cache (cache_key, payload, status, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                cache_key,
                json.dumps(translations, ensure_ascii=False),
                status,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
