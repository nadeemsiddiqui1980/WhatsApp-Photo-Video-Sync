from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import signal
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Event
from typing import Iterable, Optional

from change_logger import ChangeLogger
from config_loader import load_config
from media_pipeline import build_date_folder, is_allowed_media, move_with_collision_safe_name, sha256_file
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


def _normalized_ext_set(values: Optional[Iterable[str]]) -> set[str]:
    if not values:
        return set()
    return {v.lower() for v in values}


def _as_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if not normalized or "${" in normalized:
            return default
        return normalized in {"1", "true", "yes", "on", "y"}
    if isinstance(value, (int, float)):
        return value != 0
    return default


def _as_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return default
        if normalized.startswith("${") and normalized.endswith("}"):
            return default
        try:
            return int(normalized)
        except ValueError:
            return default
    return default


def _upload_pending_parallel(
    state: StateStore,
    uploader: SFTPUploader,
    change_log: ChangeLogger,
    upload_retries: int,
    upload_retry_base: int,
    worker_count: int,
    max_inflight: int,
    batch_limit_per_cycle: int,
    delete_local_after_upload: bool,
) -> tuple[int, int]:
    pending = state.iter_pending_uploads()
    if not pending:
        return 0, 0

    limited_pending = pending[:batch_limit_per_cycle]
    deferred_count = len(pending) - len(limited_pending)
    if deferred_count > 0:
        logging.info(
            "Pending uploads exceed cycle batch limit. Deferring %s file(s) to later cycles.",
            deferred_count,
        )

    def _upload_one(task: tuple[str, str, str]) -> tuple[str, str, Optional[str], Optional[Exception]]:
        sha256_hash, local_path, grouped_date = task
        try:
            remote_path = _upload_with_retry(
                uploader,
                local_path,
                grouped_date,
                upload_retries,
                upload_retry_base,
            )
            return sha256_hash, local_path, remote_path, None
        except Exception as exc:  # noqa: BLE001
            return sha256_hash, local_path, None, exc

    uploaded_count = 0
    failed_count = 0
    safe_workers = max(1, worker_count)
    safe_inflight = max(safe_workers, max_inflight)

    for offset in range(0, len(limited_pending), safe_inflight):
        chunk = limited_pending[offset : offset + safe_inflight]
        with ThreadPoolExecutor(max_workers=safe_workers) as executor:
            futures = [executor.submit(_upload_one, task) for task in chunk]
            for future in as_completed(futures):
                sha256_hash, local_path, remote_path, error = future.result()
                if error is None and remote_path is not None:
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
                    if delete_local_after_upload:
                        local_file = Path(local_path)
                        try:
                            local_file.unlink(missing_ok=True)
                            change_log.log(
                                "media",
                                "local_deleted_after_upload",
                                "ok",
                                {
                                    "sha256": sha256_hash,
                                    "local_path": local_path,
                                    "remote_path": remote_path,
                                },
                            )
                        except Exception as delete_exc:  # noqa: BLE001
                            logging.warning("Uploaded but failed to delete local file %s: %s", local_path, delete_exc)
                            change_log.log(
                                "media",
                                "local_delete_after_upload_failed",
                                "warning",
                                {
                                    "sha256": sha256_hash,
                                    "local_path": local_path,
                                    "remote_path": remote_path,
                                    "error": str(delete_exc),
                                },
                            )
                    continue

                logging.exception("Upload failed for %s", local_path, exc_info=error)
                failed_count += 1
                change_log.log(
                    "upload",
                    "sftp_upload_failed",
                    "error",
                    {
                        "sha256": sha256_hash,
                        "local_path": local_path,
                        "error": str(error),
                    },
                )

    return uploaded_count, failed_count


def _cleanup_uploaded_local_media_once(
    state: StateStore,
    change_log: ChangeLogger,
    enabled: bool,
) -> tuple[int, int]:
    if not enabled:
        return 0, 0

    removed = 0
    missing = 0
    for sha256_hash, local_path, remote_path in state.iter_uploaded_files():
        local_file = Path(local_path)
        if not local_file.exists():
            missing += 1
            continue
        try:
            local_file.unlink(missing_ok=True)
            removed += 1
            change_log.log(
                "media",
                "local_deleted_existing_uploaded",
                "ok",
                {
                    "sha256": sha256_hash,
                    "local_path": local_path,
                    "remote_path": remote_path,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logging.warning("Failed to delete existing uploaded local file %s: %s", local_path, exc)
            change_log.log(
                "media",
                "local_delete_existing_uploaded_failed",
                "warning",
                {
                    "sha256": sha256_hash,
                    "local_path": local_path,
                    "remote_path": remote_path,
                    "error": str(exc),
                },
            )

    return removed, missing


def run() -> None:
    config = load_config("config/config.yaml")
    _setup_logging(
        config["app"]["log_dir"],
        _as_int(config["app"].get("log_max_bytes", 5_242_880), 5_242_880),
        _as_int(config["app"].get("log_backup_count", 7), 7),
    )
    signal.signal(signal.SIGINT, _handle_stop_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_stop_signal)

    change_log = ChangeLogger(config["app"]["change_history_file"])
    state = StateStore(config["app"]["sqlite_db_file"])

    uploader = SFTPUploader(
        host=config["sftp"]["host"],
        port=_as_int(config["sftp"].get("port", 22), 22),
        username=config["sftp"]["username"],
        password=config["sftp"]["password"],
        remote_base=config["sftp"]["remote_base"],
        connect_timeout_seconds=_as_int(config["sftp"].get("connect_timeout_seconds", 20), 20),
    )

    wa = WhatsAppClient(
        group_name=config["whatsapp"]["group_name"],
        profile_dir=config["whatsapp"]["browser_profile_dir"],
        temp_download_dir=config["app"]["temp_download_dir"],
        allowed_download_extensions=list(
            _normalized_ext_set(config["filters"].get("image_extensions", []))
            | _normalized_ext_set(config["filters"].get("video_extensions", []))
            | _normalized_ext_set(config["filters"].get("allowed_extensions", []))
        ),
        headless=bool(config["whatsapp"]["headless"]),
        startup_timeout_seconds=_as_int(config["whatsapp"].get("startup_timeout_seconds", 180), 180),
        download_timeout_seconds=_as_int(config["whatsapp"].get("download_timeout_seconds", 30), 30),
        message_scan_limit=_as_int(config["whatsapp"].get("message_scan_limit", 30), 30),
        browser=str(config["whatsapp"].get("browser", "auto")),
    )

    poll_seconds = _as_int(config["app"].get("poll_interval_seconds", 60), 60)
    upload_retries = _as_int(config["app"].get("upload_max_retries", 5), 5)
    upload_retry_base = _as_int(config["app"].get("upload_retry_base_seconds", 2), 2)
    upload_worker_count = _as_int(config["app"].get("upload_worker_count", 2), 2)
    upload_max_inflight = _as_int(config["app"].get("upload_max_inflight", 4), 4)
    upload_batch_limit_per_cycle = _as_int(config["app"].get("upload_batch_limit_per_cycle", 20), 20)
    delete_local_after_upload = _as_bool(config["app"].get("delete_local_after_upload", False), default=False)
    cleanup_existing_uploaded_on_startup = _as_bool(
        config["app"].get("cleanup_existing_uploaded_on_startup", False),
        default=False,
    )
    quarantine_dir = Path(config["app"].get("quarantine_dir", "./state/quarantine"))
    photos_root = Path(config["app"]["photos_root"])
    videos_root = Path(config["app"].get("videos_root", "./videos"))
    image_exts = _normalized_ext_set(config["filters"].get("image_extensions", []))
    video_exts = _normalized_ext_set(config["filters"].get("video_extensions", []))
    legacy_exts = _normalized_ext_set(config["filters"].get("allowed_extensions", []))
    if not image_exts and legacy_exts:
        image_exts = legacy_exts
    if not image_exts:
        image_exts = {".jpg", ".jpeg", ".png", ".webp"}
    if not video_exts:
        video_exts = {".mp4", ".mov", ".3gp", ".m4v", ".mkv", ".webm", ".avi", ".hevc", ".h265"}
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    wa.start()
    logging.info("Collector started for group: %s", config["whatsapp"]["group_name"])
    logging.info("Continuous polling enabled: poll_interval_seconds=%s", poll_seconds)
    logging.info(
        "Upload parallelism configured: workers=%s max_inflight=%s batch_limit_per_cycle=%s",
        upload_worker_count,
        upload_max_inflight,
        upload_batch_limit_per_cycle,
    )
    logging.info("Delete local media after upload: %s", delete_local_after_upload)
    logging.info(
        "Startup cleanup for previously uploaded local media: %s",
        cleanup_existing_uploaded_on_startup,
    )
    change_log.log("system", "startup", "ok")

    removed_existing, missing_existing = _cleanup_uploaded_local_media_once(
        state,
        change_log,
        cleanup_existing_uploaded_on_startup,
    )
    if cleanup_existing_uploaded_on_startup:
        logging.info(
            "Startup cleanup complete for uploaded local media: removed=%s missing=%s",
            removed_existing,
            missing_existing,
        )
        change_log.log(
            "media",
            "startup_cleanup_uploaded_local_complete",
            "ok",
            {
                "removed": removed_existing,
                "already_missing": missing_existing,
            },
        )

    try:
        while not STOP_EVENT.is_set():
            downloaded = []
            try:
                downloaded = wa.fetch_new_media()
            except Exception as exc:  # noqa: BLE001
                logging.exception("Failed to fetch media from WhatsApp")
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
                is_image = is_allowed_media(temp_path, image_exts)
                is_video = is_allowed_media(temp_path, video_exts)
                if not is_image and not is_video:
                    change_log.log("media", "skip_unsupported_media", "ok", {"file": str(temp_path)})
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
                media_root = photos_root if is_image else videos_root
                media_type = "image" if is_image else "video"
                date_folder = build_date_folder(media_root, use_dt)
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
                        "media_type": media_type,
                    },
                )
                new_count += 1

            uploaded_delta, failed_delta = _upload_pending_parallel(
                state,
                uploader,
                change_log,
                upload_retries,
                upload_retry_base,
                upload_worker_count,
                upload_max_inflight,
                upload_batch_limit_per_cycle,
                delete_local_after_upload,
            )
            uploaded_count += uploaded_delta
            failed_count += failed_delta

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
        try:
            uploader.close_all()
        except Exception:
            pass
        change_log.log("system", "shutdown", "ok")


if __name__ == "__main__":
    run()
