# Sharing and Cleanup Guide

Use this guide before sharing the project folder with another person.

## Goal
- Share source code and documentation safely.
- Avoid sharing secrets, local runtime cache, or machine-specific artifacts.
- Keep enough files so receiver can run setup and pipeline quickly.

## Keep these files/folders
- `src/`
- `scripts/`
- `bootstrap/`
- `config/`
- `docs/`
- `README.md`
- `CHANGELOG.md`
- `PLAN.md`
- `requirements.txt`
- `app_version.json`

## Remove before sharing

### Required removal (security)
- `.env` (contains real credentials)
- Any credential backups or exports

### Recommended removal (machine/runtime artifacts)
- `.venv/`
- `state/browser_profile/`
- `state/temp_downloads/*`
- `state/quarantine/*`
- `state/change_history.jsonl`
- `state/pipeline.db`
- `logs/pipeline.log`
- Any debug outputs under `state/` (for example: `e2e_*.txt`, `post_fix_*.txt`, `run_output*.txt`, `*probe*`)

### Optional removal (if not sharing data)
- `photos/`

## Keep placeholders for receiver
- Keep `state/` folder itself (empty is fine).
- Keep `logs/` folder itself (empty is fine).
- Keep `photos/` folder if you want expected structure present.

## Safe share package steps (PowerShell)

Preferred single command:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\cleanup_share.ps1
```

Optional (exclude local photos from the package):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\cleanup_share.ps1 -IncludePhotos
```

Dry-run preview:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\cleanup_share.ps1 -WhatIf
```

Equivalent manual commands (reference only):

```powershell
# Run from project root
Remove-Item .\.env -Force -ErrorAction SilentlyContinue
Remove-Item .\.venv -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item .\state\browser_profile -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item .\state\temp_downloads\* -Force -ErrorAction SilentlyContinue
Remove-Item .\state\quarantine\* -Force -ErrorAction SilentlyContinue
Remove-Item .\state\change_history.jsonl -Force -ErrorAction SilentlyContinue
Remove-Item .\state\pipeline.db -Force -ErrorAction SilentlyContinue
Remove-Item .\logs\pipeline.log -Force -ErrorAction SilentlyContinue
```

## Receiver setup steps
1. Copy folder to destination machine.
2. Create new `.env` with receiver credentials and group name.
3. Run setup:

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap\setup.ps1
```

4. Run pipeline:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_pipeline.ps1
```

5. First run: scan WhatsApp QR.

## Polling behavior reminder
- Polling interval comes from `POLL_INTERVAL_SECONDS` in `.env`.
- Current example value is `60`, so the pipeline checks for new photos every 60 seconds.
