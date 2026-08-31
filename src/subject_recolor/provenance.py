from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import RecolorTask


def load_source_records(job_dir: Path) -> dict[str, dict[str, Any]]:
    """Load an optional SOURCES.json beside a job workspace or one level above it."""
    candidates = [
        job_dir / "SOURCES.json",
        job_dir.parent / "SOURCES.json",
        job_dir.parent.parent / "SOURCES.json",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        records = payload.get("sources", []) if isinstance(payload, dict) else []
        found: dict[str, dict[str, Any]] = {}
        for item in records:
            if not isinstance(item, dict):
                continue
            local_file = item.get("local_file")
            if not isinstance(local_file, str):
                continue
            found[Path(local_file).name.casefold()] = item
        return found
    return {}


def source_record(task: RecolorTask, job_dir: Path) -> dict[str, Any] | None:
    return load_source_records(job_dir).get(task.source.name.casefold())
