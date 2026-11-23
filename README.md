# Daymark Todo

A local, daily task manager for Windows, built with Python 3.13, CustomTkinter, and SQLite.

## Features

- Separate task list for each Gregorian date.
- Gregorian and Persian (Jalali) calendars are shown together. You can navigate by day and jump to a date using either calendar.
- Persian and Arabic-Indic numerals are accepted in date input.
- Add, edit, delete, complete, and reopen tasks.
- Nested subtasks. Deleting a task also deletes its descendants after confirmation.
- Low, Normal, and High priorities.
- Dark and light themes; the selected theme is remembered.
- Manual, consistent SQLite backups saved inside `data\backups`; the backup remains encrypted.
- Unicode task text. Persian, Arabic, English, and other Unicode text are stored as UTF-8 before encryption; the interface uses Segoe UI on Windows for broad script coverage.
- No network access, telemetry, registry writes, startup entries, or Windows settings changes.

## Requirements

- Windows 10 or 11 (64-bit recommended)
- Python 3.13.12 for running from source

## Run from source

Open Command Prompt in this folder and run:

```bat
run.bat
```

The script creates a virtual environment in `.venv`, installs the packages in `requirements.txt`, and starts the app.

You can also prepare the environment manually:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

## Build the Windows executable

Run this on Windows using Python 3.13:

```bat
build_exe.bat
```

The build produces:

```text
dist\DaymarkTodo\DaymarkTodo.exe
DaymarkTodo-Windows.zip
```

**Distribute the entire `dist\DaymarkTodo` folder**, not only the EXE. The folder contains the bundled runtime files. Users do not need Python installed.

The build script keeps its virtual environment, pip cache, temporary build directory, and PyInstaller output inside this project folder. PyInstaller is not a cross-compiler, so build the Windows executable on Windows.

For a portable installation, extract/copy the complete `DaymarkTodo` folder to a user-writable location, for example a folder under the user's home directory. Avoid `C:\Program Files` unless the user has write permission there: the app intentionally stores its database beside the EXE, not in AppData or another system location.

## Where data is stored

At runtime, the app creates:

```text
DaymarkTodo\
  DaymarkTodo.exe
  data\
    daymark.sqlite3
    backups\
      daymark_backup_*.sqlite3
```

When running from source, the same `data\daymark.sqlite3` layout is created beside `app.py`.

The database, theme preference, and all task data remain inside the app folder. SQLite uses a rollback journal in the same folder and removes it after a transaction. No task data is sent over the network.

## Encryption and important limitations

- On first launch, create a master password of at least 8 characters.
- The app derives an encryption key from that password using PBKDF2-HMAC-SHA256 with a random per-database salt and 600,000 iterations.
- Each complete task record is encrypted using Fernet before being saved. This includes the task text, date, priority, completion flag, parent relationship, and timestamps.
- Random task IDs and non-sensitive app metadata (such as the theme preference and password salt/verifier) remain visible in SQLite.
- The master password is not saved. **There is no password reset or recovery.** If it is lost, the encrypted task contents cannot be recovered.
- Encryption protects the database at rest; it does not protect text while the app is unlocked, defend against malware/keyloggers on the PC, or prevent someone with access to the running account from viewing the app.
- Use the in-app Backup button or copy the complete `data` folder after closing the app. Backups are still encrypted and require the same master password.

## Project files

- `app.py` — CustomTkinter interface and task interactions.
- `storage.py` — encrypted SQLite storage and password-based key derivation.
- `calendar_utils.py` — Gregorian/Jalali conversion and localized digit parsing.
- `requirements.txt` — runtime dependencies.
- `run.bat` — run from source on Windows.
- `build_exe.bat` — build the Windows distribution using PyInstaller.
