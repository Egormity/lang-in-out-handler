"""Private, local SQLite preferences and transcript history."""

import json
import os
import sqlite3
import threading
from pathlib import Path

from .history_sessions import combine_sessions
from .settings import Settings


def app_data_dir() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "lang-in-out-handler"


class Store:
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = Path(data_dir) if data_dir is not None else app_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.data_dir.chmod(0o700)
        self.path = self.data_dir / "history.sqlite3"
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
        self.path.chmod(0o600)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        version = self._db.execute("PRAGMA user_version").fetchone()[0]
        if version > 3:
            self._db.close()
            raise RuntimeError("This history database requires a newer version of Lang In/Out.")
        try:
            self._initialize_schema(version)
        except Exception:
            self._db.close()
            raise

    def _initialize_schema(self, version: int) -> None:
        # One schema head. Existing history is upgraded additively in the same
        # transaction as the version marker, keeping IDs, timestamps, and settings.
        with self._db:
            self._db.execute("BEGIN IMMEDIATE")
            self._db.execute("""
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            self._db.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mode TEXT NOT NULL,
                    source_text TEXT NOT NULL,
                    translated_text TEXT NOT NULL DEFAULT '',
                    source_pronunciation TEXT NOT NULL DEFAULT '',
                    translation_pronunciation TEXT NOT NULL DEFAULT '',
                    session_id TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                )
            """)
            if version < 2:
                columns = {row["name"] for row in self._db.execute("PRAGMA table_info(history)")}
                for column in ("source_pronunciation", "translation_pronunciation"):
                    if column not in columns:
                        self._db.execute(
                            f"ALTER TABLE history ADD COLUMN {column} TEXT NOT NULL DEFAULT ''"
                        )
            if version < 3:
                columns = {row["name"] for row in self._db.execute("PRAGMA table_info(history)")}
                if "session_id" not in columns:
                    self._db.execute(
                        "ALTER TABLE history ADD COLUMN session_id TEXT NOT NULL DEFAULT ''"
                    )
            self._db.execute(
                "CREATE INDEX IF NOT EXISTS history_session_order ON history(mode, session_id, id)"
            )
            self._db.execute("PRAGMA user_version=3")

    def load_settings(self) -> Settings:
        with self._lock:
            row = self._db.execute(
                "SELECT value FROM preferences WHERE key = ?", ("settings",)
            ).fetchone()
        if row is None:
            return Settings()
        try:
            value = json.loads(row["value"])
            return Settings.from_dict(value) if isinstance(value, dict) else Settings()
        except (TypeError, ValueError):
            return Settings()

    def save_settings(self, settings: Settings) -> None:
        value = json.dumps(settings.to_dict(), ensure_ascii=False)
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO preferences(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                ("settings", value),
            )

    def add_history(
        self,
        mode: str,
        source_text: str,
        translated_text: str = "",
        model: str = "",
        *,
        source_pronunciation: str = "",
        translation_pronunciation: str = "",
        session_id: str = "",
    ) -> int:
        with self._lock, self._db:
            cursor = self._db.execute(
                "INSERT INTO history(mode,source_text,translated_text,model,"
                "source_pronunciation,translation_pronunciation,session_id) VALUES(?,?,?,?,?,?,?)",
                (
                    mode,
                    source_text,
                    translated_text,
                    model,
                    source_pronunciation,
                    translation_pronunciation,
                    session_id,
                ),
            )
            return int(cursor.lastrowid)

    def update_history_translation(
        self, record_id: int, translated_text: str, source_pronunciation: str = "",
        translation_pronunciation: str = "",
    ) -> bool:
        """Revise one recognized caption without adding another history entry."""
        with self._lock, self._db:
            cursor = self._db.execute(
                "UPDATE history SET translated_text=?, source_pronunciation=?, "
                "translation_pronunciation=? WHERE id=? AND mode='output'",
                (translated_text, source_pronunciation, translation_pronunciation, record_id),
            )
            return bool(cursor.rowcount)

    def update_history_source(self, record_id: int, source_text: str) -> bool:
        """Revise a caption block in place; never recreate deleted history."""
        with self._lock, self._db:
            cursor = self._db.execute(
                "UPDATE history SET source_text=?, translated_text='', source_pronunciation='', "
                "translation_pronunciation='' WHERE id=? AND mode='output'",
                (source_text, record_id),
            )
            return bool(cursor.rowcount)

    def list_history(self, limit: int = 100) -> list[dict]:
        """Return complete sessions; the limit counts entries, never individual chunks."""
        with self._lock:
            rows = self._db.execute(
                """
                WITH recent AS (
                    SELECT mode, session_id, MIN(id) AS first_id, MAX(id) AS latest_id
                    FROM history
                    GROUP BY mode, session_id, CASE WHEN session_id='' THEN id ELSE 0 END
                    ORDER BY latest_id DESC LIMIT ?
                )
                SELECT history.* FROM history JOIN recent
                    ON history.mode=recent.mode AND history.session_id=recent.session_id
                    AND (history.session_id<>'' OR history.id=recent.first_id)
                ORDER BY recent.latest_id DESC, history.id ASC
                """,
                (max(1, min(limit, 10000)),),
            ).fetchall()
        return combine_sessions(rows)

    def list_history_segments(
        self, limit: int = 100, *, session_id: str | None = None, mode: str | None = None
    ) -> list[dict]:
        """Inspect the stored fragments used for contextual revisions, newest first."""
        filters, values = [], []
        if session_id is not None:
            filters.append("session_id=?")
            values.append(session_id)
        if mode is not None:
            filters.append("mode=?")
            values.append(mode)
        where = " WHERE " + " AND ".join(filters) if filters else ""
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM history" + where + " ORDER BY id DESC LIMIT ?",
                (*values, max(1, min(limit, 10000))),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_history(self) -> None:
        with self._lock, self._db:
            self._db.execute("DELETE FROM history")
        # Removed text should not remain in SQLite free pages or the WAL.
        with self._lock:
            self._db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self._db.execute("VACUUM")

    def close(self) -> None:
        with self._lock:
            self._db.close()
