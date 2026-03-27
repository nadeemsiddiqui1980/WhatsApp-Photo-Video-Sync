from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from uuid import uuid4


class ChangeLogger:
    def __init__(self, history_file: str) -> None:
        self.history_path = Path(history_file)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, component: str, action: str, status: str, details: Optional[Dict[str, Any]] = None) -> None:
        event = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "component": component,
            "action": action,
            "status": status,
            "correlation_id": str(uuid4()),
            "details": details or {},
        }
        with self.history_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=True) + "\n")
