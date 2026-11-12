"""API credentials live in the desktop keyring or a private local fallback."""

import json
import os
import tempfile
from pathlib import Path

import keyring

from .storage import app_data_dir

SERVICE = "lang-in-out-handler"
ACCOUNT = "openai-api-key"


class Credentials:
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = Path(data_dir) if data_dir is not None else app_data_dir()
        self.path = self.data_dir / "credentials.json"
        self.backend_label = "No API key saved"

    def _read_fallback(self) -> str:
        if not self.path.exists():
            return ""
        if self.path.is_symlink():
            raise RuntimeError("Credential file must not be a symbolic link.")
        self.path.chmod(0o600)
        try:
            value = json.loads(self.path.read_text(encoding="utf-8")).get("api_key", "")
        except (ValueError, AttributeError):
            raise RuntimeError(
                "Saved credential file is unreadable. Save your API key again."
            ) from None
        if not isinstance(value, str):
            raise TypeError("Saved API key is invalid. Save your API key again.")
        self.backend_label = "Private local file (permissions 0600)"
        return value

    def get(self) -> str:
        # A fallback write may have happened while an older keyring item was locked.
        # The private file is authoritative until a later successful keyring save removes it.
        if self.path.exists():
            return self._read_fallback()
        try:
            value = keyring.get_password(SERVICE, ACCOUNT)
        except Exception:  # noqa: BLE001 - keyring providers use unrelated exception classes
            value = None
        if value:
            self.backend_label = "Desktop keyring"
            return value
        return self._read_fallback()

    def set(self, key: str) -> None:
        key = key.strip()
        if not key or any(character.isspace() for character in key):
            raise ValueError("Enter a nonempty API key without whitespace.")
        try:
            keyring.set_password(SERVICE, ACCOUNT, key)
            # Some null backends silently discard writes. Verify before dropping the fallback.
            if keyring.get_password(SERVICE, ACCOUNT) != key:
                raise RuntimeError("The desktop keyring did not retain the credential.")
        except Exception:  # noqa: BLE001 - keyring providers use unrelated exception classes
            self._write_fallback(key)
        else:
            self.path.unlink(missing_ok=True)
            self.backend_label = "Desktop keyring"

    def _write_fallback(self, key: str) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.data_dir.chmod(0o700)
        fd, filename = tempfile.mkstemp(prefix=".credentials-", dir=self.data_dir)
        temporary = Path(filename)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"api_key": key}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)
        self.backend_label = "Private local file (permissions 0600)"

    def delete(self) -> None:
        self.path.unlink(missing_ok=True)
        try:
            keyring.delete_password(SERVICE, ACCOUNT)
        except keyring.errors.PasswordDeleteError:
            pass
        except Exception:  # noqa: BLE001 - keyring providers use unrelated exception classes
            # Do not pretend a keyring secret was removed when the keyring is locked.
            raise RuntimeError(
                "Could not remove the key from the desktop keyring. Unlock it first."
            ) from None
        self.backend_label = "No API key saved"
