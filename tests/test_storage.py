import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from lang_handler.credentials import Credentials
from lang_handler.settings import Settings
from lang_handler.storage import Store


def test_settings_and_unicode_history_survive_restart(tmp_path):
    store = Store(tmp_path)
    settings = Settings(output_language="ja", target_language="Русский", font_size=26)
    settings.shortcuts["input"] = "Meta+Alt+D"
    store.save_settings(settings)
    record_id = store.add_history("output", "こんにちは。", "Привет.", "gpt-transcribe")
    store.close()

    reopened = Store(tmp_path)
    assert reopened.load_settings() == settings
    row = reopened.list_history()[0]
    assert row["id"] == record_id
    assert row["source_text"] == "こんにちは。"
    assert row["translated_text"] == "Привет."
    assert row["created_at"].endswith("Z")
    assert reopened.path.stat().st_mode & 0o777 == 0o600
    reopened.close()


def test_sql_text_is_data_and_delete_preserves_preferences(tmp_path):
    store = Store(tmp_path)
    settings = Settings(target_language="French")
    store.save_settings(settings)
    store.add_history("input", "'); DROP TABLE history; --")
    store.add_history("input", "second")
    assert store.list_history(1)[0]["source_text"] == "second"
    store.delete_history()
    assert store.list_history() == []
    assert store.load_settings() == settings
    store.close()


def test_threaded_history_is_serialized(tmp_path):
    store = Store(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda n: store.add_history("input", str(n)), range(30)))
    assert len(store.list_history()) == 30
    store.close()


def test_future_database_is_not_silently_downgraded(tmp_path):
    with sqlite3.connect(tmp_path / "history.sqlite3") as database:
        database.execute("PRAGMA user_version=4")
    with pytest.raises(RuntimeError, match="newer version"):
        Store(tmp_path)
    with sqlite3.connect(tmp_path / "history.sqlite3") as database:
        assert database.execute("PRAGMA user_version").fetchone()[0] == 4


def test_secret_uses_keyring_and_never_database(tmp_path, monkeypatch):
    vault = {}
    monkeypatch.setattr("keyring.get_password", lambda service, name: vault.get(name))
    monkeypatch.setattr(
        "keyring.set_password", lambda service, name, value: vault.update({name: value})
    )
    monkeypatch.setattr("keyring.delete_password", lambda service, name: vault.pop(name, None))
    credentials = Credentials(tmp_path)
    credentials.set("sk-test-only")
    assert credentials.get() == "sk-test-only"
    assert credentials.backend_label == "Desktop keyring"
    assert not credentials.path.exists()
    credentials.delete()
    assert credentials.get() == ""


def test_secret_fallback_is_private_and_overrides_locked_old_keyring(tmp_path, monkeypatch):
    def locked(*args):
        raise RuntimeError("locked")

    monkeypatch.setattr("keyring.set_password", locked)
    monkeypatch.setattr("keyring.get_password", lambda *args: "old-key")
    credentials = Credentials(tmp_path / "private")
    credentials.set("sk-new-test-only")
    assert credentials.get() == "sk-new-test-only"
    assert credentials.path.stat().st_mode & 0o777 == 0o600
    assert credentials.data_dir.stat().st_mode & 0o777 == 0o700
    assert json.loads(credentials.path.read_text())["api_key"] == "sk-new-test-only"


def test_keyring_success_cleans_stale_fallback(tmp_path, monkeypatch):
    vault = {}
    monkeypatch.setattr(
        "keyring.set_password", lambda service, name, key: vault.update({name: key})
    )
    monkeypatch.setattr("keyring.get_password", lambda service, name: vault.get(name))
    credentials = Credentials(tmp_path)
    credentials.path.write_text('{"api_key":"old"}')
    credentials.set("sk-new-test-only")
    assert not credentials.path.exists()
    assert credentials.get() == "sk-new-test-only"


def test_credentials_reject_symlink(tmp_path, monkeypatch):
    monkeypatch.setattr("keyring.get_password", lambda *args: None)
    original = tmp_path / "other"
    original.write_text('{"api_key":"other"}')
    credentials = Credentials(tmp_path)
    os.symlink(original, credentials.path)
    with pytest.raises(RuntimeError, match="symbolic link"):
        credentials.get()


def test_pronunciations_survive_restart_and_old_callers_get_empty_guides(tmp_path):
    store = Store(tmp_path)
    old_id = store.add_history("input", "Original dictation")
    result_id = store.add_history(
        "translate",
        "カフェ",
        "Café",
        "gpt-6-luna",
        source_pronunciation="Kafe",
        translation_pronunciation="/kæˈfeɪ/",
    )
    store.close()
    reopened = Store(tmp_path)
    rows = {row["id"]: row for row in reopened.list_history()}
    assert rows[result_id]["source_pronunciation"] == "Kafe"
    assert rows[result_id]["translation_pronunciation"] == "/kæˈfeɪ/"
    assert rows[old_id]["source_pronunciation"] == ""
    assert rows[old_id]["translation_pronunciation"] == ""
    reopened.close()


def test_v1_upgrade_preserves_history_preferences_and_identifiers(tmp_path):
    path = tmp_path / "history.sqlite3"
    preferences = json.dumps({"output_language": "ja", "voice": "cedar"})
    timestamp = "2026-10-15T01:02:03.456Z"
    with sqlite3.connect(path) as database:
        database.executescript("""
            CREATE TABLE preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode TEXT NOT NULL,
                source_text TEXT NOT NULL,
                translated_text TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            );
            PRAGMA user_version=1;
        """)
        database.execute("INSERT INTO preferences VALUES (?,?)", ("settings", preferences))
        database.execute(
            "INSERT INTO history VALUES (?,?,?,?,?,?)",
            (44, "output", "こんにちは", "Hello", "gpt-transcribe", timestamp),
        )
    store = Store(tmp_path)
    assert store.load_settings().voice == "cedar"
    row = store.list_history()[0]
    assert row == {
        "id": 44,
        "mode": "output",
        "source_text": "こんにちは",
        "translated_text": "Hello",
        "model": "gpt-transcribe",
        "created_at": timestamp,
        "source_pronunciation": "",
        "translation_pronunciation": "",
        "session_id": "",
        "segment_count": 1,
    }
    next_id = store.add_history(
        "translate", "日本語", "Japanese", source_pronunciation="Nihongo"
    )
    assert next_id > 44
    store.close()
    with sqlite3.connect(path) as database:
        assert database.execute("PRAGMA user_version").fetchone()[0] == 3
        assert database.execute("SELECT value FROM preferences WHERE key='settings'").fetchone()[0] == preferences
    # Reopening must not rerun an ALTER or lose the newly added text.
    reopened = Store(tmp_path)
    assert reopened.list_history()[0]["source_pronunciation"] == "Nihongo"
    assert len(reopened.list_history()) == 2
    reopened.close()


def test_new_database_uses_the_same_schema_head(tmp_path):
    store = Store(tmp_path)
    store.close()
    with sqlite3.connect(tmp_path / "history.sqlite3") as database:
        assert database.execute("PRAGMA user_version").fetchone()[0] == 3
        columns = {row[1] for row in database.execute("PRAGMA table_info(history)")}
        assert {"source_pronunciation", "translation_pronunciation", "session_id"}.issubset(columns)
