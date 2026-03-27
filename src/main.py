from __future__ import annotations

import logging
import signal
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Event

from change_logger import ChangeLogger
from config_loader import load_config
from media_pipeline import build_date_folder, is_allowed_image, move_with_collision_safe_name, sha256_file
from state_store import StateStore
from uploader_sftp import SFTPUploader
from whatsapp_client import WhatsAppClient


STOP_EVENT = Event()


def _handle_stop_signal(_signum, _frame) -> None:
    STOP_EVENT.set()


def _setup_logging(log_dir: str, max_bytes: int, backup_count: int) -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    rotating_handler = RotatingFileHandler(
        Path(log_dir) / "pipeline.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            rotating_handler,
            logging.StreamHandler(),
        ],
    )


def _upload_with_retry(
    uploader: SFTPUploader,
    local_path: str,
    grouped_date: str,
    max_retries: int,
    base_delay_seconds: int,
) -> str:
    attempt = 1
    while True:
        try:
            return uploader.upload_file(local_path, grouped_date)
        except Exception:
            if attempt >= max_retries:
                raise
            sleep_for = base_delay_seconds * (2 ** (attempt - 1))
            logging.warning(
                "Upload failed (attempt %s/%s). Retrying in %ss for %s",
                attempt,
                max_retries,
                sleep_for,
                local_path,
            )
            time.sleep(sleep_for)
            attempt += 1


def run() -> None:
    config = load_config("config/config.yaml")
    _setup_logging(
        config["app"]["log_dir"],
        int(config["app"].get("log_max_bytes", 5_242_880)),
        int(config["app"].get("log_backup_count", 7)),
    )
    signal.signal(signal.SIGINT, _handle_stop_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_stop_signal)

    change_log = ChangeLogger(config["app"]["change_history_file"])
    state = StateStore(config["app"]["sqlite_db_file"])

    uploader = SFTPUploader(
        host=config["sftp"]["host"],
        port=int(config["sftp"]["port"]),
        username=config["sftp"]["username"],
        password=config["sftp"]["password"],
        remote_base=config["sftp"]["remote_base"],
        connect_timeout_seconds=int(config["sftp"].get("connect_timeout_seconds", 20)),
    )

    wa = WhatsAppClient(
        group_name=config["whatsapp"]["group_name"],
        profile_dir=config["whatsapp"]["browser_profile_dir"],
        temp_download_dir=config["app"]["temp_download_dir"],
        headless=bool(config["whatsapp"]["headless"]),
        startup_timeout_seconds=int(config["whatsapp"].get("startup_timeout_seconds", 180)),
        download_timeout_seconds=int(config["whatsapp"].get("download_timeout_seconds", 30)),
        message_scan_limit=int(config["whatsapp"].get("message_scan_limit", 30)),
        browser=str(config["whatsapp"].get("browser", "auto")),
    )

    poll_seconds = int(config["app"]["poll_interval_seconds"])
    upload_retries = int(config["app"].get("upload_max_retries", 5))
    upload_retry_base = int(config["app"].get("upload_retry_base_seconds", 2))
    quarantine_dir = Path(config["app"].get("quarantine_dir", "./state/quarantine"))
    photos_root = Path(config["app"]["photos_root"])
    allowed_exts = config["filters"]["allowed_extensions"]
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    wa.start()
    logging.info("Collector started for group: %s", config["whatsapp"]["group_name"])
    logging.info("Continuous polling enabled: poll_interval_seconds=%s", poll_seconds)
    change_log.log("system", "startup", "ok")

    try:
        while not STOP_EVENT.is_set():
            downloaded = []
            try:
                downloaded = wa.fetch_new_images()
            except Exception as exc:  # noqa: BLE001
                logging.exception("Failed to fetch images from WhatsApp")
                change_log.log("collector", "fetch_failed", "error", {"error": str(exc)})

            new_count = 0
            uploaded_count = 0
            skipped_count = 0
            failed_count = 0

            for item in downloaded:
                temp_path = item.local_temp_path
                if not temp_path.exists():
                    logging.warning(
                        "Skipping media item because downloaded temp file is missing: message_id=%s sender=%s expected_path=%s",
                        item.message_id,
                        item.sender,
                        temp_path,
                    )
                    change_log.log(
                        "media",
                        "skip_missing_temp_file",
                        "warning",
                        {
                            "message_id": item.message_id,
                            "sender": item.sender,
                            "expected_temp_path": str(temp_path),
                        },
                    )
                    skipped_count += 1
                    continue
                if not is_allowed_image(temp_path, allowed_exts):
                    change_log.log("media", "skip_non_image", "ok", {"file": str(temp_path)})
                    temp_path.rename(quarantine_dir / temp_path.name)
                    skipped_count += 1
                    continue

                file_hash = sha256_file(temp_path)
                if state.has_hash(file_hash):
                    change_log.log("media", "skip_duplicate", "ok", {"sha256": file_hash, "file": str(temp_path)})
                    temp_path.unlink(missing_ok=True)
                    skipped_count += 1
                    continue

                use_dt = item.message_time
                date_folder = build_date_folder(photos_root, use_dt)
                dest_path = move_with_collision_safe_name(temp_path, date_folder, file_hash[:8])
                grouped_date = use_dt.strftime("%Y-%m-%d")

                now_utc = datetime.now(timezone.utc).isoformat()
                state.upsert_file(file_hash, str(dest_path), grouped_date, now_utc)
                change_log.log(
                    "media",
                    "organized",
                    "ok",
                    {
                        "sha256": file_hash,
                        "sender": item.sender,
                        "dest": str(dest_path),
                        "grouped_date": grouped_date,
                    },
                )
                new_count += 1

            for sha256_hash, local_path, grouped_date in state.iter_pending_uploads():
                try:
                    remote_path = _upload_with_retry(
                        uploader,
                        local_path,
                        grouped_date,
                        upload_retries,
                        upload_retry_base,
                    )
                    now_utc = datetime.now(timezone.utc).isoformat()
                    state.mark_uploaded(sha256_hash, remote_path, now_utc)
                    uploaded_count += 1
                    change_log.log(
                        "upload",
                        "sftp_uploaded",
                        "ok",
                        {
                            "sha256": sha256_hash,
                            "local_path": local_path,
                            "remote_path": remote_path,
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    logging.exception("Upload failed for %s", local_path)
                    failed_count += 1
                    change_log.log(
                        "upload",
                        "sftp_upload_failed",
                        "error",
                        {"sha256": sha256_hash, "local_path": local_path, "error": str(exc)},
                    )

            logging.info(
                "Cycle complete: new=%s uploaded=%s skipped=%s failed=%s",
                new_count,
                uploaded_count,
                skipped_count,
                failed_count,
            )
            change_log.log(
                "system",
                "cycle_complete",
                "ok",
                {
                    "new": new_count,
                    "uploaded": uploaded_count,
                    "skipped": skipped_count,
                    "failed": failed_count,
                },
            )
            STOP_EVENT.wait(poll_seconds)
    finally:
        wa.stop()
        change_log.log("system", "shutdown", "ok")


if __name__ == "__main__":
    run()
