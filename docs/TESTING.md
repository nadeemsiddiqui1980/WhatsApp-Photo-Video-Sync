# Production Testing Checklist

Run these tests in order.

## 0. Trust Review (Recommended)

1. Open and review these scripts before running:
- `scripts/preflight.ps1`
- `bootstrap/setup.ps1`
- `bootstrap/install_and_run.ps1`
- `scripts/run_pipeline.ps1`
- `scripts/register_task.ps1`
- `scripts/cleanup_share.ps1`

2. Confirm expected behavior against `docs/INSTRUCTIONS.md` section 3.

## 1. Preflight

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\preflight.ps1
```

Pass criteria:
- `windows.supported` is `true`
- `tools.python` is `true`
- `tools.supportedBrowser` is `true`
- `network.whatsapp443` is `true`

Note:
- `network.sftp22` can be `false` until `.env` has real `SFTP_HOST`.

## 2. Setup

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap\setup.ps1
```

Pass criteria:
- `.venv` exists
- dependencies install successfully
- `.env` exists
- `config/config.yaml` exists (auto-created from template)

## 3. Configure Environment

Edit `.env` with real values:
- `SFTP_HOST`
- `SFTP_PORT`
- `SFTP_USERNAME`
- `SFTP_PASSWORD`
- `SFTP_REMOTE_BASE`
- `WHATSAPP_GROUP_NAME`

## 4. Manual Runtime Test

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_pipeline.ps1
```

Pass criteria:
- WhatsApp Web opens
- QR login works on first run
- target group is opened
- cycle logs appear in `logs/pipeline.log`
- startup log shows polling mode with configured interval

## 4A. Single-Instance Guard

1. Ensure only one runtime process is active before testing.
2. Stop any extra terminals/runners for `scripts/run_pipeline.ps1`.

Pass criteria:
- only one pipeline process writes to `logs/pipeline.log`
- cycle timing is stable (no overlapping cycle outputs)

## 5. End-to-End Media Test

1. Send 3 test photos and 3 test videos in target group.
2. Wait one or two polling cycles.

Pass criteria:
- photo files appear under `photos/YYYY/MM/DD`
- video files appear under `videos/YYYY/MM/DD`
- `state/change_history.jsonl` has `organized` and `sftp_uploaded`
- remote HostingRaja path has same files

## 5A. Continuous Polling Test (No Restart)

1. Keep pipeline running after first successful cycle.
2. Send one additional photo to the same WhatsApp group.
3. Wait up to one poll interval.

Pass criteria:
- new photo is collected without restarting pipeline
- upload event appears for the new file in a later cycle

## 5B. Browser Fallback Startup Test

1. Set in `.env`:
	- `WHATSAPP_BROWSER=auto`
2. Start runtime.
3. If one browser fails to initialize, verify startup proceeds via fallback browser.

Pass criteria:
- runtime proceeds to collection cycle without manual browser switching
- cycle logs continue with normal polling output

## 6. Duplicate Test

1. Keep pipeline running.
2. Re-send one existing image and one existing video.

Pass criteria:
- duplicate event logged (`skip_duplicate`)
- no duplicate upload record for same hash

## 6A. Parallel Upload Boundedness Test

1. Set conservative values in `.env`:
	- `UPLOAD_WORKER_COUNT=2`
	- `UPLOAD_MAX_INFLIGHT=4`
	- `UPLOAD_BATCH_LIMIT_PER_CYCLE=20`
2. Queue multiple media files (including larger videos).
3. Observe runtime during active upload cycles.

Pass criteria:
- machine remains responsive
- uploads progress concurrently in cycles
- no hangs or runaway memory behavior

## 6B. Delete-After-Upload Test

1. Set in `.env`:
	- `DELETE_LOCAL_AFTER_UPLOAD=true`
2. Send one new photo and one new video.
3. Wait for upload completion.

Pass criteria:
- both files are uploaded to SFTP
- `state/change_history.jsonl` contains `local_deleted_after_upload` entries
- uploaded local files are removed from `photos/YYYY/MM/DD` and `videos/YYYY/MM/DD`

## 6C. Legacy Uploaded File Cleanup Test

1. Ensure there are previously uploaded files still present locally.
2. Set in `.env`:
	- `CLEANUP_EXISTING_UPLOADED_ON_STARTUP=true`
3. Start runtime and allow one cycle.
4. Set `CLEANUP_EXISTING_UPLOADED_ON_STARTUP=false` after the cleanup run.

Pass criteria:
- `state/change_history.jsonl` contains `startup_cleanup_uploaded_local_complete`
- previously uploaded local files are removed
- subsequent runs do not repeatedly sweep when setting is false

## 7. Failure and Retry Test

1. Temporarily break network or use wrong SFTP password.
2. Send image.
3. Restore network/credentials.

Pass criteria:
- `sftp_upload_failed` appears first
- later cycle uploads successfully

## 8. Reboot Persistence Test

1. Register startup task:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register_task.ps1
```

2. Reboot machine.

Pass criteria:
- task starts pipeline automatically
- no setup reinstall runs at boot

## 9. Audit Test

Check `state/change_history.jsonl` has events with:
- `timestamp_utc`
- `component`
- `action`
- `status`
- `correlation_id`

Also confirm diagnostic skip visibility:
- when a downloaded temp file is missing, event `media.skip_missing_temp_file` is present

## 10. Acceptance

System is production-ready if all tests above pass.

## 11. Share Cleanup Script Validation

Run a dry-run to verify cleanup scope before sharing:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\cleanup_share.ps1 -WhatIf
```

Pass criteria:
- `.env` is included in listed removals.
- `.venv` and runtime cache/state artifacts are included.
- organized media libraries are not removed unless `-IncludeMedia` (or legacy `-IncludePhotos`) is specified.
