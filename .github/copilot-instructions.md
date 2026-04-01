# Project Guidelines

## Environment
- Windows 10/11
- Python 3.11+
- Google Chrome or Microsoft Edge
- If browser startup fails with version/session errors, update browser and reset `state/browser_profile/` before re-authenticating QR.

## Code Style
- Keep changes minimal and localized; avoid broad refactors in automation-critical paths.
- Follow existing Python patterns in `src/`: type hints, explicit error handling, and structured logging.
- Preserve script safety guarantees in PowerShell and avoid destructive filesystem operations outside project temp/state targets.
- Prefer linking to existing docs instead of duplicating operational details.

## Architecture
- Orchestration loop and retry flow: `src/main.py`
- WhatsApp Web selectors/browser automation only: `src/whatsapp_client.py`
- Hashing, validation, and date-folder organization: `src/media_pipeline.py`
- Persistent duplicate/upload state (SQLite): `src/state_store.py`
- SFTP upload behavior: `src/uploader_sftp.py`
- Config loading and env expansion: `src/config_loader.py`

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
- Acceptance checklist:
  - docs/TESTING.md

## Conventions
- Target environment is Windows 10/11 and Python 3.11+.
- Do not add behavior that deletes organized media-library files unless explicitly enabled by config. Keep cleanup limited to `state/temp_downloads`, `state/quarantine`, and explicit share-clean flows.
- Keep auditability intact: `state/change_history.jsonl` and `logs/pipeline.log` are authoritative records.
- Keep retries/backoff behavior stable unless explicitly changing reliability strategy.
- If WhatsApp DOM changes break collection, update selectors only in `src/whatsapp_client.py` and document in `CHANGELOG.md`.
- For collector/upload count mismatches, check `media.skip_missing_temp_file` in `state/change_history.jsonl` first.

## Key References
- README.md for quick start and trust/safety expectations.
- docs/INSTRUCTIONS.md for setup flow and script side effects.
- docs/OPERATIONS.md for health checks and recovery playbooks.
- docs/TESTING.md for ordered production validation.
- docs/ISSUES_AND_FIXES.md for known failures and validated remedies.
- docs/SCRIPT_AUDIT.md for script-by-script trust review.
- docs/SHARING_AND_CLEANUP.md for secure handoff and cleanup scope.
