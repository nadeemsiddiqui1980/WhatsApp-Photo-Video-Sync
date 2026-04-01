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
4. Ensure only one pipeline process is running. Multiple instances can conflict on browser/session state and cause missed new media.
5. If Chrome fails to start ("ChromeDriver" crash error):
   - Update Chrome to the latest version: https://www.google.com/chrome/
   - Delete browser cache: `Remove-Item -Recurse .\state\browser_profile\`
   - Re-run pipeline and scan QR code again
6. If setup fails with `.venv`/`pyvenv.cfg`/dependency corruption messages:
   - Stop running project Python processes.
   - Re-run setup: `powershell -ExecutionPolicy Bypass -File .\bootstrap\setup.ps1`
   - If still failing, remove `.venv` and rerun setup.
7. If upload logs show `Authentication (password) failed`:
   - Validate `.env` SFTP values and retry runtime.
   - Pending uploads remain queued and will retry in later cycles.
8. If startup fails on selected browser:
   - Set `WHATSAPP_BROWSER=auto` in `.env` to allow runtime fallback between Edge and Chrome.
   - You can pin a browser with `WHATSAPP_BROWSER=chrome` or `WHATSAPP_BROWSER=edge` after stability is confirmed.
9. If Chrome download fails ("All download strategies failed"):
   - Verify `--disable-web-security` flag is present in `src/whatsapp_client.py` Chrome options.
   - Check `state/change_history.jsonl` for `media.skip_missing_temp_file` events.
   - The pipeline uses JS blob download as primary strategy; ensure CORS is not blocking.

## New media not detected (photo/video)
If cycle logs repeatedly show `new=0 uploaded=0 skipped=0` while new media exists in group:
1. Confirm only one runtime process is active.
2. Confirm `WHATSAPP_GROUP_NAME` exactly matches the target group name.
3. Restart runtime once to reinitialize WhatsApp Web state.
4. If issue persists, clear browser profile and re-authenticate:
   - `Remove-Item -Recurse .\state\browser_profile\`
5. Check `state/change_history.jsonl` for `media.fetch_failed` details in the same time window.
6. For videos specifically: check `DOM media summary` logs for `playIcons` count - if > 0 but `videos=0`, the scroll method may need adjustment.

## Video-specific troubleshooting
WhatsApp renders video thumbnails as `<img>` elements with play icon overlays, not `<video>` elements.
1. Check logs for `Media viewer info: type=image hasVideo=False hasPlayIcon=True` - this indicates a video thumbnail.
2. Video download flow: click play button → wait for video element → download via blob URL.
3. If video doesn't load after play click, fallback to download button click.
4. Verify `msg-video`, `media-play`, `video-pip` selectors are present in `_message_rows_with_media()`.
5. Scroll method uses 200 steps with half-viewport increments for better lazy-load coverage.

## Fast mismatch diagnosis (missing downloaded file)
If WhatsApp appears to have more media than local/SFTP:
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

Use `-IncludeMedia` when you explicitly want to exclude local photo/video data from the shared package (`-IncludePhotos` is kept as legacy compatibility).

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
- Scripts do not delete the organized media library by default; review `docs/INSTRUCTIONS.md` for exact behavior details.

## Post-upload local deletion checks
If `DELETE_LOCAL_AFTER_UPLOAD=true` is enabled:
1. Confirm event `media.local_deleted_after_upload` in `state/change_history.jsonl`.
2. Confirm uploaded local paths no longer exist.

If older uploaded files still remain locally:
1. This is expected if those files were uploaded before delete-after-upload was enabled.
2. Enable `CLEANUP_EXISTING_UPLOADED_ON_STARTUP=true` for one run.
3. Confirm event `media.startup_cleanup_uploaded_local_complete` in `state/change_history.jsonl`.
4. Set `CLEANUP_EXISTING_UPLOADED_ON_STARTUP=false` again after cleanup.
