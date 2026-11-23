"""Encrypted SQLite storage for Daymark Todo.

Only random task IDs and application settings are stored in plaintext.
The complete task payload (including dates, text, priority, completion state,
and parent relationships) is encrypted before it reaches SQLite.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import sqlite3
import sys
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


DB_FILENAME = "daymark.sqlite3"
DB_SCHEMA_VERSION = 1
PBKDF2_ITERATIONS = 600_000
VERIFIER_TEXT = b"daymark-todo-password-check:v1"


class StorageError(Exception):
    """Base class for storage-related errors."""


class AuthenticationError(StorageError):
    """Raised when the master password is incorrect."""


class DataIntegrityError(StorageError):
    """Raised when encrypted data cannot be read or verified."""


@dataclass(slots=True)
class Task:
    id: str
    date: str
    title: str
    priority: str
    completed: bool
    parent_id: str | None
    position: int
    created_at: str
    updated_at: str

    @classmethod
    def create(
        cls,
        *,
        task_date: str,
        title: str,
        priority: str,
        parent_id: str | None,
        position: int,
    ) -> "Task":
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return cls(
            id=uuid.uuid4().hex,
            date=task_date,
            title=title,
            priority=priority,
            completed=False,
            parent_id=parent_id,
            position=position,
            created_at=now,
            updated_at=now,
        )

    def with_changes(self, **changes: object) -> "Task":
        changes["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return replace(self, **changes)


class EncryptedTaskStore:
    """SQLite repository. Call setup_password() or unlock() before task access."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self._fernet: Fernet | None = None

        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(self.database_path, timeout=10)
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA secure_delete = ON")
            self._connection.execute("PRAGMA temp_store = MEMORY")
            self._connection.execute("PRAGMA journal_mode = DELETE")
            self._connection.execute("PRAGMA synchronous = FULL")
            self._connection.execute("PRAGMA busy_timeout = 5000")
            self._create_schema()
        except (OSError, sqlite3.Error) as exc:
            raise StorageError(
                "The app could not create or open its database in its own folder. "
                "Move the app to a folder where your Windows account can write files."
            ) from exc

    def _create_schema(self) -> None:
        current_version = self._connection.execute("PRAGMA user_version").fetchone()[0]
        if current_version not in (0, DB_SCHEMA_VERSION):
            raise StorageError(
                f"This database uses schema version {current_version}, "
                f"which this app version cannot open (expected {DB_SCHEMA_VERSION})."
            )
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value BLOB NOT NULL
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    payload BLOB NOT NULL
                )
                """
            )
            if current_version == 0:
                self._connection.execute(f"PRAGMA user_version = {DB_SCHEMA_VERSION}")

    def is_first_run(self) -> bool:
        salt = self._get_meta("salt")
        verifier = self._get_meta("verifier")
        metadata_count = self._connection.execute("SELECT COUNT(*) FROM metadata").fetchone()[0]
        task_count = self._connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]

        if salt is None and verifier is None and metadata_count == 0 and task_count == 0:
            return True
        if salt is None or verifier is None:
            raise DataIntegrityError(
                "The database has an incomplete encryption configuration. "
                "It was not reset, so existing encrypted tasks are preserved."
            )
        return False

    def setup_password(self, password: str) -> None:
        if not password or len(password) < 8:
            raise ValueError("Use a master password with at least 8 characters.")
        if len(password) > 1024:
            raise ValueError("The master password is too long.")
        if not self.is_first_run():
            raise StorageError("A password has already been configured for this database.")

        salt = os.urandom(16)
        fernet = Fernet(self._derive_key(password, salt))
        verifier = fernet.encrypt(VERIFIER_TEXT)

        try:
            with self._connection:
                self._set_meta("salt", base64.b64encode(salt))
                self._set_meta("verifier", verifier)
                self._set_meta("theme", b"dark")
                self._set_meta("schema", str(DB_SCHEMA_VERSION).encode("ascii"))
        except sqlite3.Error as exc:
            raise StorageError("Could not save the password configuration.") from exc

        self._fernet = fernet

    def unlock(self, password: str) -> None:
        if not password or len(password) > 1024:
            raise AuthenticationError("Enter the master password you created for this database.")
        salt_value = self._get_meta("salt")
        verifier = self._get_meta("verifier")
        if salt_value is None or verifier is None:
            raise DataIntegrityError("The password configuration is missing or damaged.")

        try:
            salt = base64.b64decode(salt_value, validate=True)
            fernet = Fernet(self._derive_key(password, salt))
            check = fernet.decrypt(verifier)
        except (ValueError, InvalidToken, TypeError) as exc:
            raise AuthenticationError("That password is incorrect.") from exc

        if not secrets.compare_digest(check, VERIFIER_TEXT):
            raise AuthenticationError("That password is incorrect.")

        try:
            result = self._connection.execute("PRAGMA quick_check").fetchone()
            if not result or result[0] != "ok":
                raise DataIntegrityError("SQLite reported a database integrity problem.")
        except sqlite3.Error as exc:
            raise DataIntegrityError("The database could not be checked.") from exc

        self._fernet = fernet

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=PBKDF2_ITERATIONS,
        )
        raw_key = kdf.derive(password.encode("utf-8"))
        return base64.urlsafe_b64encode(raw_key)

    def lock(self) -> None:
        self._fernet = None

    def _require_fernet(self) -> Fernet:
        if self._fernet is None:
            raise AuthenticationError("Unlock the app before accessing tasks.")
        return self._fernet

    def get_theme(self) -> str:
        value = self._get_meta("theme")
        if value in (b"light", b"dark"):
            return value.decode("ascii")
        return "dark"

    def set_theme(self, theme: str) -> None:
        if theme not in {"light", "dark"}:
            raise ValueError("Theme must be 'light' or 'dark'.")
        try:
            with self._connection:
                self._set_meta("theme", theme.encode("ascii"))
        except sqlite3.Error as exc:
            raise StorageError("Could not save the appearance preference.") from exc

    def get_all_tasks(self) -> list[Task]:
        fernet = self._require_fernet()
        try:
            rows = self._connection.execute("SELECT id, payload FROM tasks").fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Could not read tasks from the database.") from exc

        tasks: list[Task] = []
        for task_id, encrypted_payload in rows:
            try:
                raw = fernet.decrypt(encrypted_payload)
                payload = json.loads(raw.decode("utf-8"))
                task = Task(**payload)
                if task.id != task_id:
                    raise ValueError("Task ID mismatch")
                if task.priority not in {"Low", "Normal", "High"}:
                    raise ValueError("Invalid priority")
                tasks.append(task)
            except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise DataIntegrityError(
                    "A task record could not be decrypted or is damaged. "
                    "The database has not been modified."
                ) from exc
        return tasks

    def save_task(self, task: Task) -> None:
        fernet = self._require_fernet()
        payload = json.dumps(asdict(task), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        encrypted_payload = fernet.encrypt(payload)
        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO tasks (id, payload) VALUES (?, ?)
                    ON CONFLICT(id) DO UPDATE SET payload = excluded.payload
                    """,
                    (task.id, encrypted_payload),
                )
        except sqlite3.Error as exc:
            raise StorageError("Could not save the task.") from exc

    def delete_tasks(self, task_ids: Iterable[str]) -> None:
        self._require_fernet()
        ids = list(dict.fromkeys(task_ids))
        if not ids:
            return
        try:
            with self._connection:
                self._connection.executemany(
                    "DELETE FROM tasks WHERE id = ?",
                    ((task_id,) for task_id in ids),
                )
        except sqlite3.Error as exc:
            raise StorageError("Could not delete the selected task.") from exc

    def backup_to(self, destination: Path) -> None:
        """Create a consistent SQLite snapshot (task payloads remain encrypted)."""
        self._require_fernet()
        destination = Path(destination)
        if destination.resolve() == self.database_path.resolve():
            raise StorageError("The backup destination cannot be the live database file.")

        backup_connection: sqlite3.Connection | None = None
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            backup_connection = sqlite3.connect(destination)
            self._connection.backup(backup_connection)
            backup_connection.commit()
        except (OSError, sqlite3.Error) as exc:
            raise StorageError("Could not create the encrypted database backup.") from exc
        finally:
            if backup_connection is not None:
                backup_connection.close()

    def _get_meta(self, key: str) -> bytes | None:
        try:
            row = self._connection.execute(
                "SELECT value FROM metadata WHERE key = ?", (key,)
            ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Could not read the app configuration.") from exc
        return bytes(row[0]) if row else None

    def _set_meta(self, key: str, value: bytes) -> None:
        self._connection.execute(
            "INSERT INTO metadata (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def close(self) -> None:
        self.lock()
        try:
            self._connection.close()
        except sqlite3.Error:
            pass


def get_database_path() -> Path:
    """Return a database location inside the source folder or beside the EXE."""
    if getattr(sys, "frozen", False):
        app_folder = Path(sys.executable).resolve().parent
    else:
        app_folder = Path(__file__).resolve().parent
    data_folder = app_folder / "data"
    try:
        data_folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StorageError(
            "Daymark cannot create its data folder. Move the app to a folder "
            "where your Windows account has write permission."
        ) from exc
    return data_folder / DB_FILENAME
