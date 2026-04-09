# Photo Sync (WhatsApp Group -> SFTP)

Zero-cost open-source automation for Windows 10/11.

## What this does
- Collects new photos from one WhatsApp group (WhatsApp Web automation).
- Organizes files as `photos/YYYY/MM/DD`.
- Uploads to Your-SFTP over SFTP.
- Tracks duplicates with SQLite.
- Records change history in `state/change_history.jsonl`.
- After WhatsApp QR authentication and valid SFTP credentials are in place, the service keeps running and polls for new photos every `POLL_INTERVAL_SECONDS`.
- Emits explicit diagnostic events when a downloaded file reference is missing (`media.skip_missing_temp_file`) so count mismatches are quickly traceable.

## Trust and safety
- Setup and runtime scripts do not delete your photo library.
- `bootstrap/setup.ps1` creates `.venv`, folders, and `.env` (if missing), then installs dependencies.
- Setup auto-recovers common broken `.venv` states (missing `pyvenv.cfg`, missing `pip`, and known PyYAML corruption patterns) and fails fast with actionable diagnostics when a lock or install error occurs.
- `scripts/run_pipeline.ps1` only starts the service.
- `scripts/register_task.ps1` only creates/updates one Windows Scheduled Task.
- Runtime duplicate handling only removes duplicate temporary downloads from `state/temp_downloads`.
- Non-image files found in temp downloads are moved to `state/quarantine` (not deleted).

## Quick start
1. Open PowerShell in project root.
2. Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap\install_and_run.ps1
```

3. Edit `.env` with your values:
- `SFTP_HOST`
- `SFTP_USERNAME`
- `SFTP_PASSWORD`
- `SFTP_REMOTE_BASE`
- `WHATSAPP_GROUP_NAME`

4. First launch opens WhatsApp Web. Scan QR once.

## Manual dependency install links
- Python 3.11+ download: https://www.python.org/downloads/windows/
- Python on Windows docs: https://docs.python.org/3/using/windows.html
- Microsoft Winget docs: https://learn.microsoft.com/windows/package-manager/winget/
- Install Winget (App Installer): https://learn.microsoft.com/windows/package-manager/winget/#install-winget
- Google Chrome download: https://www.google.com/chrome/
- Microsoft Edge download: https://www.microsoft.com/edge/download
- PowerShell execution policy docs: https://learn.microsoft.com/powershell/module/microsoft.powershell.security/set-executionpolicy
- Windows Task Scheduler docs: https://learn.microsoft.com/windows/win32/taskschd/task-scheduler-start-page

## Run at startup
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register_task.ps1
```

Startup task runs `scripts/run_pipeline.ps1` (runtime only, no reinstall on boot).

## Production readiness note
The collector includes fallback selector strategies for WhatsApp Web, startup timeouts, download timeouts, retry/backoff uploads, and persistent state. If WhatsApp Web updates its DOM in the future, update selectors in `src/whatsapp_client.py`.

## Where records are kept
- Pipeline log: `logs/pipeline.log`
- Change history: `state/change_history.jsonl`
- State DB: `state/pipeline.db`

## Troubleshooting and fix history
- Known issues and resolved root causes are tracked in `docs/ISSUES_AND_FIXES.md`.

## Project layout
- `src/` core Python modules
- `scripts/` preflight/task/admin scripts
- `bootstrap/` setup and first-run scripts
- `config/` runtime config templates
- `docs/` operational notes

## Detailed instructions
- Step-by-step guide with examples and ASCII diagrams: `docs/INSTRUCTIONS.md`
- Production test checklist: `docs/TESTING.md`
- Script-by-script trust audit: `docs/SCRIPT_AUDIT.md`
- Project change record: `CHANGELOG.md`
- Sharing cleanup checklist (what to remove before handing project to others): `docs/SHARING_AND_CLEANUP.md`
- Single-command sharing cleanup script: `scripts/cleanup_share.ps1`
- Agent onboarding summary for new Copilot sessions: `AGENTS.md`
