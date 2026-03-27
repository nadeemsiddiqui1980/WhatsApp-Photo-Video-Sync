# Issues and Fixes Log

This document tracks observed problems, root causes, implemented fixes, and validation status.

## 2026-03-24

### 1. Photo collection failed with StaleElementReferenceException
- Symptoms:
  - Pipeline crashes when clicking on photo elements in WhatsApp Web with: `selenium.common.exceptions.StaleElementReferenceException: stale element reference: stale element not found in the current frame`
  - Error occurs at line 436 in `src/whatsapp_client.py` during `photo_button.click()`
- Root cause:
  - WhatsApp Web uses a virtualized DOM that changes during scroll operations.
  - Photo button element references stored in a list become invalid (stale) by the time they are iterated and clicked.
  - Scroll operations and DOM re-renders invalidate the cached element references.
- Solution provided:
  - Changed from direct photo button iteration to index-based iteration with fresh DOM queries.
  - Added retry loop (max 2 retries) that re-queries the row for photo elements before each click attempt.
  - Added `StaleElementReferenceException` to the exception handler with proper retry backoff.
  - Only appends downloaded media if `preview_opened==True` to ensure valid file path.
- Validation path:
  - Run pipeline against WhatsApp group with 5+ unread photos.
  - Monitor logs/pipeline.log for successful collection without stale element errors.
  - Verify photos/YYYY/MM/DD/ contains expected new media.

### 2. Follow-up stale crash at message row attribute access
- Symptoms:
  - Pipeline still failed in `fetch_new_images` at `message_id = row.get_attribute("data-id")` with `StaleElementReferenceException`.
  - Error line observed around `src/whatsapp_client.py:418`.
- Root cause:
  - Message row references from the original row list became stale before attribute reads due to WhatsApp DOM virtualization and reflow.
- Solution provided:
  - Switched row traversal to index-based iteration with fresh row re-query per retry.
  - Added row-level stale retry handling (`max_row_retries=2`) around `get_attribute` and downstream row operations.
  - Kept photo-level stale retries and fixed append guard to only record media when a new `downloaded_file` is produced.
- Validation path:
  - Live run processed multiple cycles with successful `new/uploaded` counts after patch.
  - No new stale-element stack trace was emitted during the successful collection cycles.

### 3. Setup failed on invalid `.venv` version parsing
- Symptoms:
  - Setup failed with `No pyvenv.cfg file` followed by version-cast failure (`Cannot convert value ".0" to type "System.Version"`).
- Root cause:
  - Existing `.venv` was partially broken and interpreter output was not a clean version string.
- Solution provided:
  - Hardened `bootstrap/setup.ps1` to auto-recreate invalid `.venv`, parse version output defensively, and fail fast with actionable diagnostics.
  - Added dependency install retries and import validation.
- Validation path:
  - `bootstrap/setup.ps1` now completes setup and reports clear errors only for actual downstream issues.

### 4. Corrupted PyYAML package state (`yaml.error` import failure)
- Symptoms:
  - Runtime failed with `ModuleNotFoundError: No module named 'yaml.error'`.
  - Setup encountered `uninstall-no-record-file` for `pyyaml` (missing RECORD metadata).
- Root cause:
  - Corrupted package metadata in `.venv` prevented clean uninstall/reinstall.
- Solution provided:
  - Added automated repair in setup with fallback install path: `--ignore-installed --no-cache-dir PyYAML==6.0.3`.
- Validation path:
  - Setup executes repair logic and proceeds without manual package surgery.

### 5. Browser startup instability with Edge/Chrome in auto mode
- Symptoms:
  - Edge startup crash (`SessionNotCreatedException`) on some runs.
  - Chrome startup crash (`DevToolsActivePort file doesn't exist`) on some runs.
- Root cause:
  - Environment-specific browser startup instability and incomplete browser discovery in some path layouts.
- Solution provided:
  - Auto browser preference adjusted to Chrome-first.
  - Browser discovery expanded with PATH fallback.
  - Added additional stability flags for Chrome and Edge startup.
- Validation path:
  - Collector startup and processing cycles observed in runtime logs after fixes.

### 6. Current operational blocker: SFTP authentication failure
- Symptoms:
  - Upload step logs `Authentication (password) failed` and `paramiko.ssh_exception.AuthenticationException`.
- Root cause:
  - SFTP credentials/host policy mismatch (not a setup/bootstrap code failure).
- Resolution guidance:
  - Verify `.env` SFTP credentials and host details.
  - Re-run runtime; pending uploads retry automatically.

## 2026-03-22

### 1. Collection mismatch (3 photos uploaded while 10 existed in WhatsApp)
- Symptoms:
  - WhatsApp group media had more items than local/SFTP totals.
  - Pipeline completed cycles but final uploaded count remained lower than expected.
- Root cause:
  - Message/media collection did not always expose enough WhatsApp virtualized rows during scan windows.
- Solution provided:
  - Strengthened chat scanning strategy in `src/whatsapp_client.py` to iterate through virtualized rows and perform upward paging passes.
  - Increased practical scan coverage via `whatsapp.message_scan_limit` configuration.
- Validation path:
  - Re-run pipeline with clean state.
  - Compare `organized` and `sftp_uploaded` counts in `state/change_history.jsonl`.

### 2. Missing explicit diagnostics for skipped missing temp files
- Symptoms:
  - A file could be skipped if the temp path did not exist, but this path was only counted, not explicitly logged.
  - Future mismatch triage was slower because there was no direct skip event for missing temp files.
- Root cause:
  - `src/main.py` only incremented `skipped_count` when `temp_path` was absent.
- Solution provided:
  - Added warning log entry with `message_id`, `sender`, and expected path.
  - Added structured change event: `media.skip_missing_temp_file` with status `warning`.
- Validation path:
  - Observe warning line in `logs/pipeline.log`.
  - Observe event in `state/change_history.jsonl`.

### 3. Need explicit confirmation of continuous unattended behavior
- Symptoms:
  - Ambiguity about whether the service auto-checks and auto-uploads after authentication.
- Root cause:
  - Behavior existed, but docs and startup logs were not explicit enough.
- Solution provided:
  - Added startup log in `src/main.py` showing active polling interval.
  - Updated `README.md`, `docs/INSTRUCTIONS.md`, `docs/OPERATIONS.md`, and `docs/TESTING.md` with clear continuous polling flow and validation steps.
- Validation path:
  - Start pipeline once, authenticate, then add a new photo and confirm upload in later cycle without restarting.

## Related records
- `CHANGELOG.md` for per-file change entries.
- `state/change_history.jsonl` for runtime event trace.
- `logs/pipeline.log` for operational logs.
- `scripts/cleanup_share.ps1` for one-command pre-share cleanup.