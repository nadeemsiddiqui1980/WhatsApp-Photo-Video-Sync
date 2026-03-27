# Operations Guide

For full setup walkthrough with examples and diagrams, see `docs/INSTRUCTIONS.md`.
For script side effects and manual dependency links, see sections 3 and 4 in `docs/INSTRUCTIONS.md`.
Script trust audit is available at `docs/SCRIPT_AUDIT.md`.
Repository change tracking is available at `CHANGELOG.md`.

## Health checks
- Preflight report: `state/preflight_report.json`
- Runtime log: `logs/pipeline.log`
- Change events: `state/change_history.jsonl`
- Polling mode: process remains active and checks for new media every `POLL_INTERVAL_SECONDS` after startup/authentication.

## Recovery
1. If upload fails, keep service running; pending records remain in SQLite and retry on next cycles.
2. If WhatsApp session expires, rerun pipeline and scan QR again.
3. To run manually without setup phase, execute `scripts/run_pipeline.ps1`.
4. If Chrome fails to start ("ChromeDriver" crash error):
   - Update Chrome to the latest version: https://www.google.com/chrome/
   - Delete browser cache: `Remove-Item -Recurse .\state\browser_profile\`
   - Re-run pipeline and scan QR code again
5. If setup fails with `.venv`/`pyvenv.cfg`/dependency corruption messages:
   - Stop running project Python processes.
   - Re-run setup: `powershell -ExecutionPolicy Bypass -File .\bootstrap\setup.ps1`
   - If still failing, remove `.venv` and rerun setup.
6. If upload logs show `Authentication (password) failed`:
   - Validate `.env` SFTP values and retry runtime.
   - Pending uploads remain queued and will retry in later cycles.

## Fast mismatch diagnosis (missing downloaded file)
If WhatsApp appears to have more photos than local/SFTP:
1. Search `state/change_history.jsonl` for `skip_missing_temp_file`.
2. Search `logs/pipeline.log` for `Skipping media item because downloaded temp file is missing`.
3. Compare counts of `media.organized` and `upload.sftp_uploaded` events for the same time window.

Example PowerShell checks:

```powershell
Select-String -Path .\state\change_history.jsonl -Pattern 'skip_missing_temp_file'
Select-String -Path .\logs\pipeline.log -Pattern 'Skipping media item because downloaded temp file is missing'
Select-String -Path .\state\change_history.jsonl -Pattern '"action":"organized"' | Measure-Object
Select-String -Path .\state\change_history.jsonl -Pattern '"action":"sftp_uploaded"' | Measure-Object
```

## Migration to another machine
1. Copy full project folder.
2. Run `bootstrap/setup.ps1`.
3. Provide `.env` values for destination machine.
4. Run `scripts/register_task.ps1`.

## Share Cleanup
Before handing this project to another person, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\cleanup_share.ps1
```

Use `-IncludePhotos` only when you explicitly want to exclude local photo data from the shared package.

## Change history format
Each line in `state/change_history.jsonl` is one JSON event:
- `timestamp_utc`
- `component`
- `action`
- `status`
- `correlation_id`
- `details`

## Security
- Do not share `.env` with credentials.
- Use least-privilege HostingRaja SFTP user.
- Scripts do not delete the organized photo library; review `docs/INSTRUCTIONS.md` for exact behavior details.
