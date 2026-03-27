# Changelog

All notable project-level changes are recorded here.

Format:
- Date (UTC)
- Category
- File(s)
- Change summary
- Performed by

## 2026-03-24 (UTC)

### Runtime Fixes
- Files: src/whatsapp_client.py
- Summary: Fixed `StaleElementReferenceException` in WhatsApp collection by hardening both message-row and photo-element iteration against virtualized DOM re-renders. The collector now re-queries message rows by index with stale retries before reading attributes, and re-queries photo elements before each click attempt. Also fixed a downloaded-file append guard to avoid accidental reuse of a previous iteration value when a retry/timed-out click does not produce a new file.
- Performed by: GitHub Copilot

### Scripts / Documentation
- Files: scripts/cleanup_share.ps1, README.md, docs/INSTRUCTIONS.md, docs/SHARING_AND_CLEANUP.md, docs/OPERATIONS.md, docs/TESTING.md, docs/SCRIPT_AUDIT.md, docs/ISSUES_AND_FIXES.md, AGENTS.md, PLAN.md, .github/copilot-instructions.md
- Summary: Added `scripts/cleanup_share.ps1` as the single pre-share cleanup command with optional `-IncludePhotos` and `-WhatIf` support. Updated project markdown documentation to reference the unified cleanup workflow and audit coverage.
- Performed by: GitHub Copilot

### Build / Runtime Fixes
- Files: bootstrap/setup.ps1
- Summary: Fixed virtual environment version validation crash when `.venv` is partially broken (e.g., missing `pyvenv.cfg`). Setup now auto-recreates invalid `.venv`, parses interpreter version output defensively, fail-fast checks external command exit codes, bootstraps pip with `ensurepip`, and emits clear error guidance when `.venv` is locked by a running process.
- Performed by: GitHub Copilot

### Build / Runtime Fixes
- Files: bootstrap/setup.ps1
- Summary: Added retry logic for `pip install -r requirements.txt` (3 attempts) and improved lock guidance for `WinError 5` scenarios where project files are in use by a running Python/pipeline process.
- Performed by: GitHub Copilot

### Build / Runtime Fixes
- Files: bootstrap/setup.ps1
- Summary: Added post-install dependency sanity checks and automatic PyYAML repair (`--force-reinstall --no-cache-dir PyYAML`) to recover from partial/corrupted package states that can cause `ModuleNotFoundError: yaml.error`.
- Performed by: GitHub Copilot

### Build / Runtime Fixes
- Files: bootstrap/setup.ps1
- Summary: Added fallback repair path for corrupted PyYAML installs missing `RECORD` metadata by retrying with `--ignore-installed --no-cache-dir PyYAML==6.0.3`.
- Performed by: GitHub Copilot

### Runtime Fixes
- Files: src/whatsapp_client.py
- Summary: Changed `whatsapp.browser=auto` selection order to prefer Chrome before Edge. This avoids startup failures on machines where Edge crashes during WebDriver session creation while Chrome is available.
- Performed by: GitHub Copilot

### Runtime Fixes
- Files: src/whatsapp_client.py
- Summary: Improved Chrome/Edge detection by adding PATH-based fallback (`shutil.which`) when default install directories are not present, so `browser=auto` can correctly choose Chrome-first on more Windows setups.
- Performed by: GitHub Copilot

### Runtime Fixes
- Files: src/whatsapp_client.py
- Summary: Added additional Chrome/Edge startup stability flags (`--no-sandbox`, `--disable-dev-shm-usage`, `--disable-gpu`, `--disable-software-rasterizer`, and pipe transport where applicable) to reduce browser crash-on-start scenarios.
- Performed by: GitHub Copilot

### Documentation
- Files: README.md, docs/INSTRUCTIONS.md, docs/OPERATIONS.md, docs/ISSUES_AND_FIXES.md
- Summary: Updated troubleshooting and operations guidance to reflect setup auto-recovery behavior (`.venv`/PyYAML repair), browser startup fallback behavior, and current SFTP authentication diagnostics. Removed duplicated historical sections in `docs/ISSUES_AND_FIXES.md`.
- Performed by: GitHub Copilot

## 2026-03-22 (UTC)

### Documentation / Handoff
- Files: docs/SHARING_AND_CLEANUP.md, AGENTS.md, README.md
- Summary: Added a safe sharing/cleanup guide (what to delete before sharing, including `.env`, `.venv`, runtime artifacts), added agent onboarding notes for faster context transfer in new Copilot sessions, and linked both documents from README.
- Performed by: GitHub Copilot

### Runtime Diagnostics
- Files: src/main.py
- Summary: Added explicit warning log and structured change-history event (`media.skip_missing_temp_file`) when a downloaded temp file is missing during processing. Added startup log for active polling interval (`poll_interval_seconds`) to make unattended loop behavior explicit.
- Performed by: GitHub Copilot

### Documentation
- Files: README.md, docs/INSTRUCTIONS.md, docs/OPERATIONS.md, docs/TESTING.md, docs/ISSUES_AND_FIXES.md
- Summary: Documented continuous polling behavior after authentication, added mismatch diagnosis steps for missing temp files, added continuous polling test case, and created a dedicated issue/solution tracker for operational history.
- Performed by: GitHub Copilot

### Build / Runtime Fixes
- Files: src/whatsapp_client.py
- Summary: Added Chrome/Edge startup flags (--no-sandbox, --disable-dev-shm-usage, --disable-gpu, etc.) for reliable browser automation. Added exception handling with version mismatch diagnostic guidance.
- Performed by: GitHub Copilot

### Build / Runtime Fixes
- Files: src/change_logger.py, src/whatsapp_client.py, src/main.py, src/config_loader.py, src/media_pipeline.py, src/state_store.py, src/uploader_sftp.py
- Summary: Added `from __future__ import annotations` and replaced union type syntax (`A | B`) with `Optional` for Python 3.8/3.9 compatibility. All annotation evaluation is now postponed to runtime.
- Performed by: GitHub Copilot

### Build / Runtime Fixes
- Files: src/config_loader.py
- Summary: Fixed relative path resolution to use project root instead of current working directory. Pipeline can now be launched from any directory and still locate config/config.yaml correctly.
- Performed by: GitHub Copilot

### Build / Runtime Fixes
- Files: bootstrap/setup.ps1
- Summary: Improved Python 3.11+ launcher detection with py.exe, python, and python3 fallback support. Added version validation guard. Auto-creates config.yaml from template if missing. Enhanced error messaging.
- Performed by: GitHub Copilot

### Build / Runtime Fixes
- Files: scripts/preflight.ps1
- Summary: Improved Python detection error handling with fallback to python3 and clearer version reporting.
- Performed by: GitHub Copilot

### Workspace Configuration
- Files: .github/copilot-instructions.md
- Summary: Created workspace instruction file with build commands, architecture boundaries, conventions, and key reference docs for consistent agent behavior.
- Performed by: GitHub Copilot

### Documentation
- Files: docs/INSTRUCTIONS.md, docs/TESTING.md, docs/SCRIPT_AUDIT.md, CHANGELOG.md, PLAN.md
- Summary: Updated all documentation to reflect Python 3.11+ requirement, config.yaml auto-creation during setup, and improved build system diagnostics.
- Performed by: GitHub Copilot

## 2026-03-17 (UTC)

### Documentation
- Files: docs/SCRIPT_AUDIT.md
- Summary: Added trust-focused script audit document with side effects, risk levels, and non-destructive guarantees.
- Performed by: GitHub Copilot (GPT-5.3-Codex)

### Documentation
- Files: CHANGELOG.md
- Summary: Added repository-level changelog to track all future updates.
- Performed by: GitHub Copilot (GPT-5.3-Codex)

### Documentation
- Files: README.md, docs/INSTRUCTIONS.md, docs/OPERATIONS.md
- Summary: Added references to script audit and explicit change-recording policy.
- Performed by: GitHub Copilot (GPT-5.3-Codex)
