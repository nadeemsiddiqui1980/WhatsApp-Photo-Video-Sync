from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional


class StateStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                    sha256 TEXT PRIMARY KEY,
                    local_path TEXT NOT NULL,
                    grouped_date TEXT NOT NULL,
                    uploaded INTEGER NOT NULL DEFAULT 0,
                    remote_path TEXT,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def has_hash(self, sha256_hash: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM files WHERE sha256 = ?", (sha256_hash,)).fetchone()
            return row is not None

    def upsert_file(self, sha256_hash: str, local_path: str, grouped_date: str, created_at_utc: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO files (sha256, local_path, grouped_date, uploaded, created_at_utc, updated_at_utc)
                VALUES (?, ?, ?, 0, ?, ?)
                ON CONFLICT(sha256) DO UPDATE SET
                  local_path=excluded.local_path,
                  grouped_date=excluded.grouped_date,
                  updated_at_utc=excluded.updated_at_utc
                """,
                (sha256_hash, local_path, grouped_date, created_at_utc, created_at_utc),
            )
            conn.commit()

    def mark_uploaded(self, sha256_hash: str, remote_path: str, updated_at_utc: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE files SET uploaded=1, remote_path=?, updated_at_utc=? WHERE sha256=?",
                (remote_path, updated_at_utc, sha256_hash),
            )
            conn.commit()

    def iter_pending_uploads(self) -> list[tuple[str, str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT sha256, local_path, grouped_date FROM files WHERE uploaded=0"
            ).fetchall()
            return [(r[0], r[1], r[2]) for r in rows]

    def get_remote_path(self, sha256_hash: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT remote_path FROM files WHERE sha256=?", (sha256_hash,)).fetchone()
            return row[0] if row and row[0] else None
