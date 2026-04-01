# Issues and Fixes Log

This document tracks observed problems, root causes, implemented fixes, and validation status.

## 2026-04-01

### 7. Chrome download failures - CORS blocking fetch of WhatsApp CDN media URLs
- Symptoms:
  - `_click_download()` JS fetch failed with "Failed to fetch" for HTTPS media URLs.
  - Download button click also failed with "All download strategies failed".
  - No media files downloaded despite correct selectors.
- Root cause:
  - WhatsApp media URLs served from CDN domains (media-bru2-1.cdn.whatsapp.net) are cross-origin.
  - Fetch API cannot access cross-origin resources without CORS headers, even with credentials.
  - Canvas extraction also failed due to tainted canvas (CORS).
- Solution provided:
  - Added `--disable-web-security` and `--disable-features=IsolateOrigins,site-per-process` Chrome flags.
  - Rewrote `_click_download()` with multi-tier strategy:
    1. Video detection via play icon overlay, click play to load video, then blob download.
    2. JS fetch+blob download for both HTTPS and blob URLs.
    3. Native download button click with expanded XPath selectors.
  - For videos: click play button, poll for video element to load, then download via blob URL.
  - For photos: direct fetch+blob download from image src.
- Validation path:
  - Live run processed photos and videos successfully.
  - `Triggered download via JS blob method: https_blob_download` in logs.
  - `Triggered video download via JS method: blob_video_download` for videos.
  - SFTP upload events present for all organized media.

### 8. Video detection failing - only photos detected, videos missed
- Symptoms:
  - Pipeline found media rows but only processed photos.
  - Videos showed `playIcons=2` in DOM summary but `videos=0`.
  - WhatsApp renders video thumbnails as `<img>` elements with play icon overlays, not `<video>` elements.
- Root cause:
  - `_message_rows_with_media()` used XPath that didn't match video-specific selectors.
  - JS returned DOM nodes that couldn't be serialized back to Selenium WebElements.
  - Video rows contain `SPAN:msg-video`, `SPAN:media-play`, `SPAN:video-pip` elements.
- Solution provided:
  - Added `msg-video`, `media-play`, `video-pip` selectors to media detection.
  - Changed JS to return message IDs instead of DOM nodes, then resolve via Selenium XPath.
  - Increased scroll steps from 50 to 200 with half-viewport steps for better lazy-load coverage.
  - Added video-specific download flow: detect play icon → click play → wait for video element → blob download.
- Validation path:
  - Live run detected 3 media rows (1 photo + 2 videos).
  - `Video loaded after 1 attempts: blob:https://web.whatsapp.com/...` in logs.
  - Both videos organized to `videos/YYYY/MM/DD/` and uploaded to SFTP.

### 9. Browser startup crashes - stale Chrome processes holding profile locks
- Symptoms:
  - Chrome crashed on startup with "crashed" error.
  - Profile directory locked by zombie Chrome processes from previous runs.
- Root cause:
  - Previous pipeline runs didn't clean up Chrome processes properly.
  - Chrome profile directory (`state/browser_profile`) held by orphaned processes.
- Solution provided:
  - Added `_kill_stale_browser_processes()` method that runs `taskkill /F /IM chrome.exe /T` and `taskkill /F /IM msedge.exe /T` before browser startup.
  - Added 1-second delay after process termination to allow file handle release.
- Validation path:
  - Pipeline starts reliably after cleanup_share.ps1 -IncludeMedia.
  - No startup crashes observed in subsequent runs.

### 10. SFTP upload reliability - new transport per file causing connection overhead
- Symptoms:
  - Each file upload created a new SSH transport, increasing latency.
  - LSP type errors for `from_transport()` returning Optional[SFTPClient].
- Root cause:
  - `SFTPUploader.upload_file()` created new `paramiko.Transport` per call.
  - No connection reuse across parallel upload workers.
  - Type annotations didn't account for None returns.
- Solution provided:
  - Implemented thread-safe connection reuse with `_thread_sftp` dict keyed by thread ID.
  - Added connection health check before reuse, automatic reconnect if stale.
  - Added `close_all()` method for graceful shutdown.
  - Added null safety checks for `from_transport()` and `stat()` return values.
  - Added `uploader.close_all()` call in `main.py` shutdown finally block.
- Validation path:
  - SFTP upload events present for all organized media.
  - `Authentication (password) successful!` in logs.
  - No connection errors during parallel uploads.

## 2026-03-31

### 0. New media at recent timestamps was missed and viewer got stuck after multi-download
- Symptoms:
  - New media shared around recent timestamps (for example 21:50 windows) was not detected.
  - Collector sometimes did not return cleanly from preview when processing multiple media tiles.
  - Some cycles showed `new=0 uploaded=0 skipped=0` despite new group activity.
- Root cause:
  - Media row discovery depended too heavily on a single row pattern and could miss some WhatsApp DOM variants.
  - Preview close/back handling was not robust enough for certain multi-media viewer states.
  - Strict chat refocus could fail when left pane/search UI was hidden.
- Solution provided:
  - Added media-node-to-message-row fallback resolution for broader DOM compatibility.
  - Hardened preview close routine with ESC and close/back button fallbacks.
  - Made chat refocus best-effort so collection continues in active chat if sidebar/search controls are unavailable.
  - Added startup browser fallback behavior so runtime can proceed if one browser crashes at startup.
- Validation path:
  - Post-fix cycles processed new media again (`new>0`, `uploaded>0`) with image/video `organized`, `sftp_uploaded`, and `local_deleted_after_upload` events.
  - No persistent `new=0 uploaded=0 skipped=0` pattern after clean single-instance rerun.

### 1. New photos/videos were not reliably detected in active WhatsApp group
- Symptoms:
  - Only older media rows were repeatedly collected.
  - Newly shared photos/videos were sometimes missed.
- Root cause:
  - Virtualized row identity and scroll-container handling in WhatsApp Web were not robust enough for all row render states.
  - Some rows were marked seen too early in certain failure paths.
- Solution provided:
  - Hardened scroll-container resolution and reacquisition during paging.
  - Improved row identity fallback when `data-id` is absent.
  - Tightened seen-row handling so rows are not finalized before successful media extraction.
- Validation path:
  - Live cycles showed fresh image and video `organized` + `sftp_uploaded` events.
  - No new `fetch_failed` events in subsequent cycles.

### 2. Uploaded local videos/photos from earlier runs remained on disk
- Symptoms:
  - Files uploaded in earlier cycles were still present in `photos/YYYY/MM/DD` or `videos/YYYY/MM/DD`.
- Root cause:
  - `DELETE_LOCAL_AFTER_UPLOAD` only affects new uploads after the setting is enabled.
- Solution provided:
  - Added optional one-time startup cleanup setting: `CLEANUP_EXISTING_UPLOADED_ON_STARTUP`.
  - Added events: `media.local_deleted_existing_uploaded` and `media.startup_cleanup_uploaded_local_complete`.
- Validation path:
  - Enable startup cleanup for one run and verify removal events in `state/change_history.jsonl`.
  - Confirm local files are removed, then set startup cleanup back to `false`.

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