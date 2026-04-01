# Photo Sync (WhatsApp Group -> HostingRaja)

Zero-cost open-source automation for Windows 10/11.

## What this does
- Collects new photos and videos from one WhatsApp group (WhatsApp Web automation).
- Organizes photos as `photos/YYYY/MM/DD` and videos as `videos/YYYY/MM/DD`.
- Uploads pending media to HostingRaja over SFTP.
- Tracks duplicates with SQLite.
- Records change history in `state/change_history.jsonl`.
- Uses bounded parallel upload workers to reduce video upload latency while keeping low-RAM machines responsive.
- After WhatsApp QR authentication and valid SFTP credentials are in place, the service keeps running and polls for new media every `POLL_INTERVAL_SECONDS`.
- Emits explicit diagnostic events when a downloaded file reference is missing (`media.skip_missing_temp_file`) so count mismatches are quickly traceable.

## Trust and safety
- Setup and runtime scripts do not delete your photo/video library by default.
- `bootstrap/setup.ps1` creates `.venv`, folders, and `.env` (if missing), then installs dependencies.
- Setup auto-recovers common broken `.venv` states (missing `pyvenv.cfg`, missing `pip`, and known PyYAML corruption patterns) and fails fast with actionable diagnostics when a lock or install error occurs.
- `scripts/run_pipeline.ps1` only starts the service.
- `scripts/register_task.ps1` only creates/updates one Windows Scheduled Task.
- Runtime duplicate handling only removes duplicate temporary downloads from `state/temp_downloads`.
- Unsupported media files found in temp downloads are moved to `state/quarantine` (not deleted).
- Optional behavior: set `DELETE_LOCAL_AFTER_UPLOAD=true` to remove local organized media files after successful SFTP upload.
- `DELETE_LOCAL_AFTER_UPLOAD` applies to new successful uploads after it is enabled.
- To remove previously uploaded local files that still exist, set `CLEANUP_EXISTING_UPLOADED_ON_STARTUP=true` for one run, then set it back to `false`.

## Rollback Safety (Before Video Rollout)

Use a rollback checkpoint before feature rollout. Development is done on branch `video-code`; create both a stable branch and an immutable tag on the last known-good photo-only commit.

```powershell
git branch stable/photos-only-2026-03-31
git tag -a v1-photo-stable-2026-03-31 -m "Photo-only stable baseline"
git push origin stable/photos-only-2026-03-31
git push origin v1-photo-stable-2026-03-31
```

Detailed runbook: `docs/ROLLBACK_INSTRUCTIONS.md`

```text
[Stable Commit]
	|
	+--> stable/photos-only-2026-03-31   (recovery branch)
	|
	+--> v1-photo-stable-2026-03-31      (immutable tag)
```

## Media and Upload Flow (ASCII)

```text
WhatsApp Group
	|
	v
Download to state/temp_downloads (sequential collector)
	|
	+--> image extension? --- yes ---> photos/YYYY/MM/DD ---> upload queue
	|
	+--> video extension? --- yes ---> videos/YYYY/MM/DD ---> upload queue
	|
	+--> unsupported -----------------> state/quarantine

Upload queue
	|
	v
Bounded parallel workers (resource-aware)
	|
	+--> Worker 1 -> SFTP -> mark uploaded
	+--> Worker 2 -> SFTP -> mark uploaded
	+--> Worker N -> SFTP -> mark uploaded
```

## Bounded Parallel Defaults

Use conservative defaults for lower-memory machines:

- 4 GB RAM: `UPLOAD_WORKER_COUNT=2`, `UPLOAD_MAX_INFLIGHT=4`, `UPLOAD_BATCH_LIMIT_PER_CYCLE=20`
- 8 GB RAM: `UPLOAD_WORKER_COUNT=3`, `UPLOAD_MAX_INFLIGHT=6`, `UPLOAD_BATCH_LIMIT_PER_CYCLE=30`

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
- `WHATSAPP_BROWSER` (`auto`, `chrome`, or `edge`)
- `LOCAL_PHOTOS_ROOT`
- `LOCAL_VIDEOS_ROOT`
- `DELETE_LOCAL_AFTER_UPLOAD`
- `CLEANUP_EXISTING_UPLOADED_ON_STARTUP`

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

Operational note:
- Run a single pipeline instance at a time. Multiple concurrent runs can race on browser/session state and produce inconsistent detection results.

## Production readiness note
The collector includes fallback selector strategies for WhatsApp Web, startup timeouts, download timeouts, retry/backoff uploads, and persistent state. If WhatsApp Web updates its DOM in the future, update selectors in `src/whatsapp_client.py`.

## Where records are kept
- Pipeline log: `logs/pipeline.log`
- Change history: `state/change_history.jsonl`
- State DB: `state/pipeline.db`

## Troubleshooting and fix history
- Known issues and resolved root causes are tracked in `docs/ISSUES_AND_FIXES.md`.
- Latest fixes (2026-04-01): Chrome CORS bypass for media downloads, video detection via play icon overlay, SFTP connection reuse, stale browser process cleanup.

## Latest fixes (2026-04-01)
- **Chrome download failures**: Fixed CORS blocking by adding `--disable-web-security` flag and rewriting download strategy with JS blob method.
- **Video detection**: Fixed detection of video thumbnails (rendered as `<img>` with play icons) by adding `msg-video`/`media-play` selectors and play-click-then-download flow.
- **SFTP reliability**: Implemented thread-safe connection reuse instead of creating new transport per file.
- **Browser stability**: Added stale process cleanup before startup to prevent profile lock crashes.

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
- Rollback runbook for humans and agents: `docs/ROLLBACK_INSTRUCTIONS.md`
- Project change record: `CHANGELOG.md`
- Sharing cleanup checklist (what to remove before handing project to others): `docs/SHARING_AND_CLEANUP.md`
- Single-command sharing cleanup script: `scripts/cleanup_share.ps1`
- Optional media-inclusive share cleanup: `powershell -ExecutionPolicy Bypass -File .\scripts\cleanup_share.ps1 -IncludeMedia`
- Agent onboarding summary for new Copilot sessions: `AGENTS.md`
