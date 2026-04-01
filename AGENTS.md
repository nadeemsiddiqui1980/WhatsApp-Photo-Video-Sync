# Agent Onboarding Notes

Quick onboarding companion for agentic coding agents.
Canonical workspace instructions live in `.github/copilot-instructions.md`.

## Read first (in order)
1. `README.md`
2. `.github/copilot-instructions.md`
3. `docs/INSTRUCTIONS.md`
4. `docs/TESTING.md`
5. `docs/ISSUES_AND_FIXES.md`
6. `CHANGELOG.md`

## Project objective
- Collect new photos and videos from one WhatsApp group (WhatsApp Web automation via Selenium).
- Organize in `photos/YYYY/MM/DD` and `videos/YYYY/MM/DD`.
- Upload to SFTP (HostingRaja) with bounded parallel workers.
- Preserve audit logs (`state/change_history.jsonl`) and dedup state (`state/pipeline.db`).

## Core boundaries
- Orchestration and polling loop: `src/main.py`
- WhatsApp selectors/browser automation: `src/whatsapp_client.py`
- Dedup and upload state (SQLite): `src/state_store.py`
- Hashing, date-folder organization: `src/media_pipeline.py`
- SFTP upload behavior: `src/uploader_sftp.py`
- Config loading and env expansion: `src/config_loader.py`
- Structured event logging: `src/change_logger.py`

## Build & Run Commands

All commands run from project root on Windows 10/11 with PowerShell.

| Command | Purpose |
|---------|---------|
| `powershell -ExecutionPolicy Bypass -File .\scripts\preflight.ps1` | Environment readiness check |
| `powershell -ExecutionPolicy Bypass -File .\bootstrap\setup.ps1` | Full setup: venv, deps, folders, .env, config |
| `powershell -ExecutionPolicy Bypass -File .\bootstrap\install_and_run.ps1` | One-command setup + first run |
| `powershell -ExecutionPolicy Bypass -File .\scripts\run_pipeline.ps1` | Runtime only (no setup) |
| `powershell -ExecutionPolicy Bypass -File .\scripts\register_task.ps1` | Register Windows Scheduled Task |
| `powershell -ExecutionPolicy Bypass -File .\scripts\cleanup_share.ps1` | Pre-share cleanup (add `-IncludeMedia` for media removal) |

Runtime entry point: `Push-Location src; & ..\.venv\Scripts\python.exe main.py; Pop-Location`

Debug single module: `Push-Location src; & ..\.venv\Scripts\python.exe <module>.py; Pop-Location`

## Testing

No formal test framework (no pytest, unittest, or conftest.py). All testing is manual
acceptance testing following the ordered checklist in `docs/TESTING.md`.

Key test scenarios:
- **End-to-end media**: Send 3 photos + 3 videos, verify organized folders and SFTP upload
- **Continuous polling**: Send new media while pipeline runs; verify collection without restart
- **Duplicate detection**: Re-send existing media; verify `skip_duplicate` in change_history.jsonl
- **Parallel upload boundedness**: Verify machine stays responsive under concurrent uploads
- **Browser fallback**: Set `WHATSAPP_BROWSER=auto`; verify Chrome/Edge fallback works
- **Delete-after-upload**: Set `DELETE_LOCAL_AFTER_UPLOAD=true`; verify local file removal post-upload

## Code Style Guidelines

### Imports
- First line: `from __future__ import annotations`
- Order: stdlib → third-party → local (not strictly separated by blank lines)
- Use `from typing import Optional, Dict, List, Any, Iterable`
- Prefer `Optional[X]` over `X | None` for Python 3.8/3.9 compatibility

### Types
- Full type hints on all function signatures (parameters and return types)
- Explicit `-> None` for void returns
- `@dataclass` for simple data containers (e.g., `DownloadedMedia`)
- Tuple/list return types spelled out: `-> tuple[int, int]`, `-> list[tuple[str, str, str]]`

### Formatting
- 4-space indentation
- Double quotes for strings
- Blank line between methods, two blank lines between top-level functions/classes
- No trailing commas in function signatures
- No strict line-length limit enforced

### Naming
- `snake_case` for functions, methods, variables, module-level constants
- `PascalCase` for classes (e.g., `StateStore`, `SFTPUploader`, `ChangeLogger`)
- `_` prefix for private methods and helper functions (e.g., `_connect`, `_init_db`, `_as_bool`)
- `UPPER_SNAKE_CASE` for module-level constants (e.g., `STOP_EVENT`)

### Error handling
- Use specific `try/except` types where possible
- For broad catches: `except Exception as exc:  # noqa: BLE001`
- Use `logging.exception()` when logging exceptions (includes traceback)
- Use `logging.warning()` for non-fatal issues
- Raise `RuntimeError` for critical config/init failures
- Use `missing_ok=True` with `Path.unlink()` for safe cleanup

### Logging
- stdlib `logging` module with `RotatingFileHandler`
- Format: `"%(asctime)s | %(levelname)s | %(message)s"`
- Output to both `logs/pipeline.log` and console (`StreamHandler`)
- Structured events go to `state/change_history.jsonl` via `ChangeLogger`

### Config
- YAML config with `${ENV_VAR}` template expansion via `string.Template.safe_substitute`
- `python-dotenv` loads `.env` before config expansion
- Defensive parsing with `_as_bool()` and `_as_int()` helpers that handle missing/invalid values

### PowerShell conventions
- `param()` blocks with typed parameters
- `$ErrorActionPreference = "Stop"` at top of scripts
- `Join-Path` for cross-version path construction
- `Push-Location`/`Pop-Location` for directory context management

## Critical constraints
- Do not add behavior that deletes organized media library files (`photos/`, `videos/`) unless explicitly enabled by config.
- Keep cleanup limited to `state/temp_downloads`, `state/quarantine`, and share-clean flows.
- Keep retries/backoff stable unless reliability strategy change is requested.
- If WhatsApp selectors break, update only `src/whatsapp_client.py` and document in `CHANGELOG.md`.
- All code and documentation changes must add a `CHANGELOG.md` entry.
- Single-instance operation — only one pipeline process at a time.

## Known issues and diagnostics
- **SFTP authentication failures**: Check `.env` credentials (`SFTP_HOST`, `SFTP_USERNAME`, `SFTP_PASSWORD`). Uploads auto-retry with exponential backoff. See `docs/ISSUES_AND_FIXES.md` section 6.
- **Chrome download instability**: `_click_download()` uses JavaScript-based media fetch as primary path to bypass Chrome download mechanism. Fallback to XPath download button click. Monitor `media.skip_missing_temp_file` events in `state/change_history.jsonl`.
- **Browser fallback**: If `WHATSAPP_BROWSER=auto`, startup tries Chrome first, then Edge.
- **Startup log**: Shows polling mode and interval in `logs/pipeline.log`.

## Where to check problems first
- Runtime log: `logs/pipeline.log`
- Event history: `state/change_history.jsonl`
- DB state: `state/pipeline.db`

## Operational shortcuts
- Safe pre-share cleanup: `powershell -ExecutionPolicy Bypass -File .\scripts\cleanup_share.ps1`
- Include media in cleanup: add `-IncludeMedia` flag
- Dry-run preview: add `-WhatIf` flag

## Verification baseline
- Follow `docs/TESTING.md` in order.
- Confirm continuous polling test (no restart) passes.
- Confirm duplicate detection works (`skip_duplicate` in change_history.jsonl).
- Confirm SFTP upload events present for all organized media.
