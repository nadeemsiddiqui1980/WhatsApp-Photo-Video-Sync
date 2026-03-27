# Agent Onboarding Notes

This file helps any new coding agent quickly understand the project without missing key points.

## Read first (in order)
1. `README.md`
2. `docs/INSTRUCTIONS.md`
3. `docs/TESTING.md`
4. `docs/ISSUES_AND_FIXES.md`
5. `CHANGELOG.md`
6. `.github/copilot-instructions.md`

## Project objective
- Collect new photos from one WhatsApp group.
- Organize in `photos/YYYY/MM/DD`.
- Upload to SFTP.
- Preserve audit logs and dedup state.

## Runtime behavior
- Main loop is in `src/main.py`.
- After authentication, process stays alive and polls on interval.
- Poll interval is controlled by `.env` key `POLL_INTERVAL_SECONDS`.

## Critical constraints
- Do not add behavior that deletes organized photo library files.
- Keep cleanup limited to temp/quarantine/state artifacts unless user explicitly requests more.
- Keep retries/backoff stable unless reliability strategy change is requested.
- If WhatsApp selectors break, update only `src/whatsapp_client.py` and document in `CHANGELOG.md`.

## Known diagnostics
- Missing temp file skip event: `media.skip_missing_temp_file` in `state/change_history.jsonl`.
- Startup log shows polling mode and interval in `logs/pipeline.log`.

## Where to check problems first
- Runtime log: `logs/pipeline.log`
- Event history: `state/change_history.jsonl`
- DB state: `state/pipeline.db`

## Operational shortcuts
- Safe pre-share cleanup command: `powershell -ExecutionPolicy Bypass -File .\scripts\cleanup_share.ps1`
- Optional photo removal for share package: add `-IncludePhotos`

## Verification baseline
- Follow `docs/TESTING.md` in order.
- Confirm continuous polling test (no restart) passes.
