"""Private, local SQLite preferences and transcript history."""

import json
import os
import sqlite3
import threading
from pathlib import Path

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
        if version > 2:
            self._db.close()
            raise RuntimeError("This history database requires a newer version of Lang In/Out.")
        try:
            self._initialize_schema(version)
        except Exception:
            self._db.close()
            raise

    def _initialize_schema(self, version: int) -> None:
        # One schema head. Existing v1 history is upgraded additively in the same
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
            self._db.execute("PRAGMA user_version=2")

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
    ) -> int:
        with self._lock, self._db:
            cursor = self._db.execute(
                "INSERT INTO history(mode,source_text,translated_text,model,"
                "source_pronunciation,translation_pronunciation) VALUES(?,?,?,?,?,?)",
                (
                    mode,
                    source_text,
                    translated_text,
                    model,
                    source_pronunciation,
                    translation_pronunciation,
                ),
            )
            return int(cursor.lastrowid)

    def list_history(self, limit: int = 100) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM history ORDER BY id DESC LIMIT ?", (max(1, min(limit, 10000)),)
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
