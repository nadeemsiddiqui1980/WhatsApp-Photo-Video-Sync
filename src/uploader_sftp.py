from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
import posixpath
import stat
import threading

import paramiko


class SFTPUploader:
    """Thread-safe SFTP uploader with connection reuse and retry support.

    Each thread gets its own SFTP connection to avoid sharing state across
    parallel upload workers. Connections are lazily created and reused within
    the same thread.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        remote_base: str,
        connect_timeout_seconds: int = 20,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.remote_base = remote_base.rstrip("/") or "/"
        self.connect_timeout_seconds = connect_timeout_seconds
        self._lock = threading.Lock()
        self._thread_sftp: dict[int, tuple[paramiko.Transport, paramiko.SFTPClient]] = {}

    def _get_sftp(self) -> tuple[paramiko.Transport, paramiko.SFTPClient]:
        """Return (transport, sftp) for the current thread, creating if needed."""
        tid = threading.get_ident()
        with self._lock:
            entry = self._thread_sftp.get(tid)
            if entry is not None:
                transport, sftp = entry
                try:
                    sftp.listdir(".")
                    return transport, sftp
                except Exception:
                    try:
                        transport.close()
                    except Exception:
                        pass
                    del self._thread_sftp[tid]

        transport = paramiko.Transport((self.host, self.port))
        transport.banner_timeout = self.connect_timeout_seconds
        transport.auth_timeout = self.connect_timeout_seconds
        transport.connect(username=self.username, password=self.password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        if sftp is None:
            transport.close()
            raise RuntimeError("Failed to create SFTP client from transport")
        with self._lock:
            self._thread_sftp[tid] = (transport, sftp)
        return transport, sftp

    def _ensure_remote_dir(self, sftp: paramiko.SFTPClient, remote_dir: str) -> None:
        current = ""
        for part in remote_dir.strip("/").split("/"):
            if not part:
                continue
            current = f"{current}/{part}"
            try:
                attr = sftp.stat(current)
                if attr is not None and attr.st_mode is not None:
                    if not stat.S_ISDIR(attr.st_mode):
                        raise RuntimeError(f"Remote path exists but is not directory: {current}")
            except FileNotFoundError:
                sftp.mkdir(current)

    def upload_file(self, local_path: str, grouped_date: str) -> str:
        local = Path(local_path)
        remote_dir = posixpath.join(self.remote_base, grouped_date.replace("-", "/"))
        remote_path = posixpath.join(remote_dir, local.name)

        _, sftp = self._get_sftp()
        self._ensure_remote_dir(sftp, remote_dir)
        sftp.put(str(local), remote_path)
        uploaded = sftp.stat(remote_path)
        if uploaded is not None and uploaded.st_size is not None:
            if uploaded.st_size != local.stat().st_size:
                raise RuntimeError(f"Upload size mismatch for {local}")
        return remote_path

    def close_all(self) -> None:
        """Close all thread-local SFTP connections."""
        with self._lock:
            for tid, (transport, sftp) in list(self._thread_sftp.items()):
                try:
                    sftp.close()
                except Exception:
                    pass
                try:
                    transport.close()
                except Exception:
                    pass
            self._thread_sftp.clear()
