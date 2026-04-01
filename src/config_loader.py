from __future__ import annotations

import os
from pathlib import Path
from string import Template
from typing import Any, Dict

import yaml
from dotenv import load_dotenv


def _expand_env(text: str) -> str:
    return Template(text).safe_substitute(os.environ)


def _resolve_project_paths(data: Dict[str, Any], project_root: Path) -> None:
    app_paths = [
        "temp_download_dir",
        "photos_root",
        "videos_root",
        "quarantine_dir",
        "log_dir",
        "change_history_file",
        "sqlite_db_file",
    ]
    app_cfg = data.get("app", {})
    for key in app_paths:
        value = app_cfg.get(key)
        if isinstance(value, str):
            p = Path(value)
            if not p.is_absolute():
                app_cfg[key] = str((project_root / p).resolve())

    wa_cfg = data.get("whatsapp", {})
    browser_profile_dir = wa_cfg.get("browser_profile_dir")
    if isinstance(browser_profile_dir, str):
        p = Path(browser_profile_dir)
        if not p.is_absolute():
            wa_cfg["browser_profile_dir"] = str((project_root / p).resolve())


def load_config(config_path: str = "config/config.yaml") -> Dict[str, Any]:
    load_dotenv()
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    # Resolve path relative to project root, not relative to current working directory
    # If config_path is relative, make it relative to the parent of this script's directory (src/)
    path = Path(config_path)
    if not path.is_absolute():
        path = project_root / config_path
    
    raw = path.read_text(encoding="utf-8")
    expanded = _expand_env(raw)
    data = yaml.safe_load(expanded)
    _resolve_project_paths(data, project_root)
    return data
