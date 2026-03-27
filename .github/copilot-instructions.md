# Project Guidelines

## Environment Requirements
- Windows 10/11
- Python 3.11+ (required for type annotation features used throughout codebase)
- Google Chrome (latest version) or Microsoft Edge (latest version) — must match ChromeDriver bundled with Selenium
  - ChromeDriver version mismatch causes `SessionNotCreatedException: Chrome failed to start: crashed`
  - Update browser and delete `state/browser_profile/` to reset then re-scan QR

## Code Style
- Keep changes minimal and localized; avoid broad refactors in automation-critical paths.
- Follow existing Python style in src modules: type hints, explicit error handling, and structured logging.
- Most Python source files use `from __future__ import annotations` for Python 3.8+ compatibility.
- Preserve script safety guarantees in PowerShell: avoid destructive filesystem operations outside temporary directories.
- Prefer updating existing docs instead of duplicating operational instructions.

## Architecture
- Orchestration lives in src/main.py and coordinates polling, organization, uploads, and retries.
- WhatsApp automation is isolated to src/whatsapp_client.py. Keep selector and browser-specific logic there.
- File hashing, validation, and date-folder organization are in src/media_pipeline.py.
- Persistent duplicate/upload state is stored in SQLite through src/state_store.py.
- SFTP behavior is isolated to src/uploader_sftp.py.
- Config loading and env expansion are in src/config_loader.py.

## Build And Test
- One-command setup and first run:
  - powershell -ExecutionPolicy Bypass -File .\bootstrap\install_and_run.ps1
- Setup only:
  - powershell -ExecutionPolicy Bypass -File .\bootstrap\setup.ps1
- Runtime only:
  - powershell -ExecutionPolicy Bypass -File .\scripts\run_pipeline.ps1
- Preflight checks:
  - powershell -ExecutionPolicy Bypass -File .\scripts\preflight.ps1
- Startup task registration:
  - powershell -ExecutionPolicy Bypass -File .\scripts\register_task.ps1
- Pre-share cleanup:
  - powershell -ExecutionPolicy Bypass -File .\scripts\cleanup_share.ps1
- Use docs/TESTING.md as the ordered acceptance checklist.

## Conventions
- Target environment is Windows 10/11 and Python 3.11+.
- Do not add behavior that deletes user photo-library files. Keep cleanup limited to state/temp_downloads and quarantine flows.
- Keep auditability intact: state/change_history.jsonl and logs/pipeline.log should remain authoritative records.
- Keep retries/backoff behavior stable unless explicitly changing reliability strategy.
- If WhatsApp DOM changes break collection, update selectors only in src/whatsapp_client.py and document the change in CHANGELOG.md.

## Key References
- README.md for quick start and trust/safety expectations.
- docs/INSTRUCTIONS.md for script side effects, setup flow, and operations.
- docs/TESTING.md for production readiness validation.
- docs/SCRIPT_AUDIT.md for script-by-script behavior review.
