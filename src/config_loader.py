from __future__ import annotations

import os
from pathlib import Path
from string import Template
from typing import Any, Dict

import yaml
from dotenv import load_dotenv


def _expand_env(text: str) -> str:
    return Template(text).safe_substitute(os.environ)


def load_config(config_path: str = "config/config.yaml") -> Dict[str, Any]:
    load_dotenv()
    # Resolve path relative to project root, not relative to current working directory
    # If config_path is relative, make it relative to the parent of this script's directory (src/)
    path = Path(config_path)
    if not path.is_absolute():
        # Get the project root (parent of src/)
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        path = project_root / config_path
    
    raw = path.read_text(encoding="utf-8")
    expanded = _expand_env(raw)
    data = yaml.safe_load(expanded)
    return data
