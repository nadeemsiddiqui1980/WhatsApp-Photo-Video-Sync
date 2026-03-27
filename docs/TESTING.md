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

## 5. End-to-End Photo Test

1. Send 3 test photos in target group.
2. Wait one or two polling cycles.

Pass criteria:
- files appear under `photos/YYYY/MM/DD`
- `state/change_history.jsonl` has `organized` and `sftp_uploaded`
- remote HostingRaja path has same files

## 5A. Continuous Polling Test (No Restart)

1. Keep pipeline running after first successful cycle.
2. Send one additional photo to the same WhatsApp group.
3. Wait up to one poll interval.

Pass criteria:
- new photo is collected without restarting pipeline
- upload event appears for the new file in a later cycle

## 6. Duplicate Test

1. Keep pipeline running.
2. Re-send one existing image.

Pass criteria:
- duplicate event logged (`skip_duplicate`)
- no duplicate upload record for same hash

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
- organized photo library is not removed unless `-IncludePhotos` is specified.
