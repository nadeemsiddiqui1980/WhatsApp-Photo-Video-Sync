# Script Audit (Trust and Side-Effect Review)

This document explains exactly what each script does, what it changes, and what it never does.

## Scope
- Project: Photo-Sync
- Platform: Windows 10/11
- Last reviewed: 2026-03-24

## 1. scripts/preflight.ps1

Purpose:
- Validates environment readiness before setup/runtime.

Actions:
- Detects OS support (Windows 10/11)
- Detects Python, Winget, Chocolatey
- Detects Chrome and Edge
- Checks network reachability for WhatsApp and SFTP host (if configured)
- Writes report to state/preflight_report.json

Creates/updates:
- state/preflight_report.json

Never does:
- Does not install software
- Does not modify photos
- Does not delete files

Risk level:
- Low

## 2. bootstrap/setup.ps1

Purpose:
- One-time environment setup.

Actions:
- Runs preflight
- Installs missing Python/browser when possible
- Validates Python version is 3.11+
- Creates virtual environment (.venv) if missing
- Installs Python dependencies
- Creates required runtime folders
- Creates .env from .env.example if missing
- Creates config/config.yaml from config/config.template.yaml if missing

Creates/updates:
- .venv/
- logs/
- state/
- photos/
- .env (only if missing)
- config/config.yaml (only if missing)

Never does:
- Does not delete organized photo library
- Does not remove user files outside project
- Does not override existing config.yaml

Risk level:
- Medium (installs dependencies and writes setup files)

## 3. bootstrap/install_and_run.ps1

Purpose:
- Convenience script for first run.

Actions:
- Runs bootstrap/setup.ps1
- Starts runtime service via scripts/run_pipeline.ps1

Creates/updates:
- Same artifacts as setup, then runtime logs/state

Never does:
- Does not schedule startup task automatically
- Does not delete organized photo library

Risk level:
- Medium

## 4. scripts/run_pipeline.ps1

Purpose:
- Runtime-only launcher.

Actions:
- Validates .venv and .env existence
- Starts src/main.py using project venv

Creates/updates:
- Runtime logs and state (through Python pipeline)

Never does:
- Does not reinstall dependencies
- Does not modify startup tasks

Risk level:
- Low

## 5. scripts/register_task.ps1

Purpose:
- Enables auto-start at boot.

Actions:
- Creates/updates one scheduled task: PhotoSyncPipeline
- Points task to scripts/run_pipeline.ps1

Creates/updates:
- Windows Task Scheduler entry (system task metadata)

Never does:
- Does not run setup at every boot
- Does not modify photo content

Risk level:
- Medium (system scheduler change)

## 6. scripts/export_config.ps1

Purpose:
- Exports shareable config template for migration.

Actions:
- Copies config/config.yaml to config/config.shareable.yaml

Creates/updates:
- config/config.shareable.yaml

Never does:
- Does not export .env secrets automatically
- Does not delete files

Risk level:
- Low

## 7. scripts/cleanup_share.ps1

Purpose:
- Pre-share cleanup using one command.

Actions:
- Removes `.env` and `.venv`
- Removes runtime artifacts from `state/` and `logs/`
- Removes mirrored runtime artifacts under `src/state/` and `src/logs/` when present
- Removes debug output files under state folders (`e2e_*.txt`, `post_fix_*.txt`, `run_output*.txt`, `*probe*`)
- Keeps placeholder directories (`state/`, `logs/`, `photos/`) for receiver readiness
- Optional: removes photo library only when `-IncludePhotos` is explicitly passed

Creates/updates:
- Ensures placeholder directories exist after cleanup

Never does:
- Does not remove organized photo library unless `-IncludePhotos` is requested
- Does not access paths outside project root

Risk level:
- Medium (destructive inside project root by design for share packaging)

## Browser and automation notes
- WhatsApp Web automation uses Selenium with Chrome or Edge WebDriver.
- ChromeDriver version must match installed Chrome version. Mismatch causes silent browser crashes.
- Browser profile cached at state/browser_profile/ preserves WhatsApp Web login session between runs.
- First run requires manual QR code scan on phone.
- If browser won't start: update to latest Chrome/Edge and delete state/browser_profile/, then re-run.

## Runtime data handling notes
- Duplicate temporary files in state/temp_downloads may be removed after dedup checks.
- Non-image temporary files are moved to state/quarantine.
- Organized library under photos/YYYY/MM/DD is preserved.

## Audit approval checklist
- Read scripts before execution.
- Confirm only expected paths are written.
- Confirm no destructive file operations in scripts.
- Run preflight first on every new machine.
