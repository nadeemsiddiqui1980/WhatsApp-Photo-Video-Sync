from __future__ import annotations

from pathlib import Path
import posixpath
import stat

import paramiko


class SFTPUploader:
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

    def _ensure_remote_dir(self, sftp: paramiko.SFTPClient, remote_dir: str) -> None:
        current = ""
        for part in remote_dir.strip("/").split("/"):
            if not part:
                continue
            current = f"{current}/{part}"
            try:
                attr = sftp.stat(current)
                if not stat.S_ISDIR(attr.st_mode):
                    raise RuntimeError(f"Remote path exists but is not directory: {current}")
            except FileNotFoundError:
                sftp.mkdir(current)

    def upload_file(self, local_path: str, grouped_date: str) -> str:
        local = Path(local_path)
        remote_dir = posixpath.join(self.remote_base, grouped_date.replace("-", "/"))
        remote_path = posixpath.join(remote_dir, local.name)

        transport = paramiko.Transport((self.host, self.port))
        try:
            transport.banner_timeout = self.connect_timeout_seconds
            transport.auth_timeout = self.connect_timeout_seconds
            transport.connect(username=self.username, password=self.password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            self._ensure_remote_dir(sftp, remote_dir)
            sftp.put(str(local), remote_path)
            uploaded = sftp.stat(remote_path)
            if uploaded.st_size != local.stat().st_size:
                raise RuntimeError(f"Upload size mismatch for {local}")
            return remote_path
        finally:
            transport.close()
