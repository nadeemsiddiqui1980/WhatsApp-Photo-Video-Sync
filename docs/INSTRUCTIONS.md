# Step-by-Step Instruction Guide

This guide is designed for first-time users on Windows 10/11 and explains exactly what each script does before you run it.

## 1. What You Need Before Starting

- Windows 10 or Windows 11
- Internet connection
- HostingRaja SFTP credentials
- WhatsApp account active on your phone
- This project folder on your machine

## 2. Architecture Diagram (ASCII)

```text
Friends send photos in WhatsApp group
                |
                v
+-----------------------------------------+
| WhatsApp Web Collector (Selenium)       |
| - Opens WhatsApp Web                    |
| - Reads one group only                  |
| - Downloads new photos                  |
+--------------------+--------------------+
                     |
                     v
+-----------------------------------------+
| Local Processing                         |
| - Validate image type                    |
| - Generate file hash                     |
| - De-duplicate with SQLite               |
| - Save to photos/YYYY/MM/DD              |
+--------------------+--------------------+
                     |
                     v
+-----------------------------------------+
| SFTP Upload to HostingRaja              |
| - Create remote date folders             |
| - Upload pending files                   |
| - Verify file size after upload          |
+--------------------+--------------------+
                     |
                     v
+-----------------------------------------+
| Audit + Logs                             |
| - state/change_history.jsonl             |
| - logs/pipeline.log                      |
| - state/pipeline.db                      |
+-----------------------------------------+
```

## 3. Build Trust First (Read Before Running Any Script)

### Script behavior and side effects

| Script | What it does | Creates/updates | Deletes files? |
|---|---|---|---|
| `scripts/preflight.ps1` | Checks OS, tools, browser, network | `state/preflight_report.json` | No |
| `bootstrap/setup.ps1` | Runs preflight, installs deps, creates venv/folders | `.venv`, `.env` (if missing), `config/config.yaml` (if missing), `logs/`, `state/`, `photos/` | No |
| `bootstrap/install_and_run.ps1` | Runs setup then starts runtime service | Same as setup + service process | No |
| `scripts/run_pipeline.ps1` | Starts pipeline only | Runtime logs/events | No |
| `scripts/register_task.ps1` | Creates/updates startup scheduled task | One task named `PhotoSyncPipeline` | No |
| `scripts/export_config.ps1` | Copies config for sharing | `config/config.shareable.yaml` | No |
| `scripts/cleanup_share.ps1` | Cleans secrets/runtime artifacts before sharing | Removes `.env`, runtime cache, logs, state DB/history; keeps placeholder folders | No (unless `-IncludePhotos`) |

Important runtime behavior:
- Duplicate temporary image files are removed from `state/temp_downloads` after dedup check.
- Non-image temp files are moved to `state/quarantine`.
- Organized photo library in `photos/YYYY/MM/DD` is not deleted by scripts.

## 4. Manual Dependency Downloads and Reference Articles

Use these if you prefer manual install before running scripts.

- Python 3.11+ (download): https://www.python.org/downloads/windows/
- Python on Windows (official docs): https://docs.python.org/3/using/windows.html
- Winget overview (Microsoft): https://learn.microsoft.com/windows/package-manager/winget/
- Install Winget (Microsoft): https://learn.microsoft.com/windows/package-manager/winget/#install-winget
- Google Chrome download: https://www.google.com/chrome/
- Microsoft Edge download: https://www.microsoft.com/edge/download
- PowerShell execution policy (Microsoft): https://learn.microsoft.com/powershell/module/microsoft.powershell.security/set-executionpolicy
- Windows Task Scheduler (Microsoft): https://learn.microsoft.com/windows/win32/taskschd/task-scheduler-start-page

## 5. One-Time Setup

From project root, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap\install_and_run.ps1
```

What this does in order:
1. Runs `scripts/preflight.ps1`
2. Verifies Python 3.11+ and browser prerequisites
3. Creates `.venv` if missing
4. Installs Python packages from `requirements.txt`
5. Creates runtime folders
6. Creates `.env` from `.env.example` if missing
7. Creates `config/config.yaml` from `config/config.template.yaml` if missing
8. Starts the pipeline using `scripts/run_pipeline.ps1`

## 6. Configure .env (with clear examples)

Open `.env` and set values.

```env
SFTP_HOST=sftp.example-hostingraja.in
SFTP_PORT=22
SFTP_USERNAME=my_sftp_user
SFTP_PASSWORD=my_sftp_password
SFTP_REMOTE_BASE=/photos
WHATSAPP_GROUP_NAME=Family Album
POLL_INTERVAL_SECONDS=60
BROWSER_PROFILE_DIR=./state/browser_profile
LOCAL_PHOTOS_ROOT=./photos
UPLOAD_MAX_RETRIES=5
UPLOAD_RETRY_BASE_SECONDS=2
WHATSAPP_STARTUP_TIMEOUT_SECONDS=180
WHATSAPP_DOWNLOAD_TIMEOUT_SECONDS=30
```

### What these two values mean

1. `BROWSER_PROFILE_DIR=./state/browser_profile`
- Purpose: stores browser session data (cookies/login/session).
- Benefit: you do QR scan once; next runs reuse login.
- `./state/browser_profile` means folder inside project root.
- Absolute example: `BROWSER_PROFILE_DIR=D:/PhotoSyncData/browser_profile`

2. `LOCAL_PHOTOS_ROOT=./photos`
- Purpose: root folder where organized photos are saved.
- Resulting structure: `./photos/YYYY/MM/DD/...`
- Absolute example: `LOCAL_PHOTOS_ROOT=D:/FamilyPhotos`

If `LOCAL_PHOTOS_ROOT=D:/FamilyPhotos`, output looks like:

```text
D:/FamilyPhotos/
  2026/
    03/
      17/
        IMG_1001_a1b2c3d4.jpg
        IMG_1002_f9e8d7c6.jpg
```

## 7. First Run and QR Login

1. Script opens WhatsApp Web.
2. Scan QR using phone.
3. Wait until chat list appears.
4. Service opens target group and starts polling.

## 8. Enable Auto-Start on Boot

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register_task.ps1
```

What happens:
- Creates/updates scheduled task `PhotoSyncPipeline`.
- Task runs `scripts/run_pipeline.ps1` at startup.
- Setup is not re-run on each boot.

## 9. Daily Flow Diagram (ASCII)

```text
[Every poll interval]
      |
      v
Open target group and scan latest image messages
      |
      +--> No new images -> Sleep -> Next cycle
      |
      v
Download image to state/temp_downloads
      |
      v
Hash + duplicate check in SQLite
      |
      +--> Duplicate temp file -> remove temp -> continue
      |
      v
Move image to photos/YYYY/MM/DD
      |
      v
Upload pending files to HostingRaja via SFTP
      |
      +--> Upload fail -> keep pending for retry
      |
      v
Write change event + logs
      |
      v
Sleep -> Next cycle
```

Runtime note:
- Authentication is front-loaded: after first successful WhatsApp login (QR) and valid SFTP credentials, the process remains active and repeats this flow every `POLL_INTERVAL_SECONDS`.

## 10. Verify It Is Working

### Local checks
- `photos/YYYY/MM/DD/` contains downloaded images
- `logs/pipeline.log` has cycle entries
- `state/change_history.jsonl` has timestamped action records

### Remote checks
- HostingRaja server has `/photos/YYYY/MM/DD`
- Uploaded file sizes match local file sizes

## 11. Example Change History Event

Each line in `state/change_history.jsonl` is one JSON object.

```json
{"timestamp_utc":"2026-03-17T10:15:22.100000+00:00","component":"upload","action":"sftp_uploaded","status":"ok","correlation_id":"9f5d0c31-96c3-4c28-beb1-1f8e1d6b3d30","details":{"sha256":"abc...","local_path":"photos/2026/03/17/image_a1b2c3d4.jpg","remote_path":"/photos/2026/03/17/image_a1b2c3d4.jpg"}}
```

## 12. Troubleshooting

1. Python not found
- Install manually from links above, then re-run setup.

2. Browser not found
- Install Chrome or Edge manually, then re-run setup.
- Chrome: https://www.google.com/chrome/
- Edge: https://www.microsoft.com/edge/download

3. Chrome crashed when starting automation (SessionNotCreatedException)
- **Root cause**: ChromeDriver version doesn't match your Chrome browser version.
- **Fix**:
  1. Update Chrome to the latest version: https://www.google.com/chrome/
  2. Delete the browser profile cache: `Remove-Item -Recurse .\state\browser_profile\`
  3. Re-run the pipeline: `powershell -ExecutionPolicy Bypass -File .\scripts\run_pipeline.ps1`
  4. Scan QR code again on first run.

4. WhatsApp session expired
- Run `scripts/run_pipeline.ps1`, then scan QR again.

5. Upload failures
- Verify `.env` SFTP values.
- Confirm port 22 is reachable.
- Check `logs/pipeline.log` and `state/change_history.jsonl`.

6. Group not detected
- Confirm exact `WHATSAPP_GROUP_NAME`.
- If WhatsApp Web UI changed, update selectors in `src/whatsapp_client.py`.
- Document the change in `CHANGELOG.md`.

7. Mismatch: WhatsApp shows more photos than uploaded count
- Check for `media.skip_missing_temp_file` events in `state/change_history.jsonl`.
- Check warning logs in `logs/pipeline.log` containing `Skipping media item because downloaded temp file is missing`.
- If missing-temp warnings are absent but counts are still low, review the scroll/media collection behavior in `src/whatsapp_client.py` and compare with `docs/ISSUES_AND_FIXES.md`.

8. Setup fails with virtual environment errors (`No pyvenv.cfg file` / version parse errors)
- **Symptoms**:
  - Setup fails during `.venv` validation with messages like `No pyvenv.cfg file`.
  - Version parsing fails while checking Python 3.11+ compatibility.
- **Fix**:
  1. Close any running pipeline/python process for this project.
  2. Re-run setup: `powershell -ExecutionPolicy Bypass -File .\bootstrap\setup.ps1`
  3. If still blocked, delete `.venv` and rerun setup.

9. Setup/runtime fails with `ModuleNotFoundError: No module named 'yaml.error'`
- **Root cause**: partially corrupted PyYAML in `.venv`.
- **Fix**:
      1. Re-run setup: `powershell -ExecutionPolicy Bypass -File .\bootstrap\setup.ps1`
      2. If it persists, remove `.venv` and run setup again.

10. Upload authentication failed (`paramiko.ssh_exception.AuthenticationException`)
- **Root cause**: invalid SFTP credentials or host-side auth rejection.
- **Fix**:
      1. Verify `.env`: `SFTP_HOST`, `SFTP_PORT`, `SFTP_USERNAME`, `SFTP_PASSWORD`, `SFTP_REMOTE_BASE`.
      2. Confirm username/password by testing with your SFTP client.
      3. Re-run runtime: `powershell -ExecutionPolicy Bypass -File .\scripts\run_pipeline.ps1`

## 13. Reuse on Another Windows Machine

1. Copy full project folder.
2. Install dependencies manually (optional) or run setup script.
3. Update `.env` values.
4. Register startup task.
5. Validate with Section 10 checks.

## 14. Security and Best Practices

- Use dedicated low-privilege SFTP account.
- Never share `.env`.
- Rotate SFTP password periodically.
- Backup `state/pipeline.db` and `state/change_history.jsonl`.
- Review scripts before running if your organization requires script approval.

## 15. Additional Trust and Change Tracking

- Script audit document: `docs/SCRIPT_AUDIT.md`
- Project-level change log: `CHANGELOG.md`
- Runtime event log (automated): `state/change_history.jsonl`
- Problem/solution timeline: `docs/ISSUES_AND_FIXES.md`

Policy for future updates:
- Every code or documentation change must add an entry to `CHANGELOG.md` with UTC date, files changed, and summary.

## 16. Safe Share Cleanup (Single Command)

Use this command from project root before sharing the folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\cleanup_share.ps1
```

Optional (only when you explicitly want to exclude local photos from the shared package):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\cleanup_share.ps1 -IncludePhotos
```

Dry-run preview:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\cleanup_share.ps1 -WhatIf
```
