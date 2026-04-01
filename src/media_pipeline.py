from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_allowed_image(path: Path, allowed_extensions: Iterable[str]) -> bool:
    return path.suffix.lower() in {e.lower() for e in allowed_extensions}


def is_allowed_media(path: Path, allowed_extensions: Iterable[str]) -> bool:
    return path.suffix.lower() in {e.lower() for e in allowed_extensions}


def build_date_folder(root: Path, dt: datetime) -> Path:
    target = root / f"{dt.year:04d}" / f"{dt.month:02d}" / f"{dt.day:02d}"
    target.mkdir(parents=True, exist_ok=True)
    return target


def move_with_collision_safe_name(src: Path, dest_dir: Path, hash_prefix: str) -> Path:
    base = src.stem
    ext = src.suffix.lower()
    dest = dest_dir / f"{base}_{hash_prefix}{ext}"
    if dest.exists():
        counter = 1
        while True:
            candidate = dest_dir / f"{base}_{hash_prefix}_{counter}{ext}"
            if not candidate.exists():
                dest = candidate
                break
            counter += 1
    shutil.move(str(src), str(dest))
    return dest
