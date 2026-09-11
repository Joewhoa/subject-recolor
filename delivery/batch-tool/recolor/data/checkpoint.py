"""Atomic checkpoint and append-only request event log."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..utils.files import atomic_write_json

SCHEMA_VERSION = 1
TERMINAL_STATUSES = {"succeeded", "failed_safe", "uncertain", "rejected"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CheckpointStore:
    def __init__(self, checkpoint_path: Path, events_path: Path):
        self.checkpoint_path = checkpoint_path
        self.events_path = events_path
        self.state: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.checkpoint_path.exists():
            return {
                "schema_version": SCHEMA_VERSION,
                "created_at": utc_now(),
                "updated_at": utc_now(),
                "run": {},
                "tasks": {},
            }
        try:
            data = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"断点文件损坏，请先人工检查：{self.checkpoint_path}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("tasks"), dict):
            raise ValueError(f"断点格式无效：{self.checkpoint_path}")
        return data

    def initialize(self, run_info: dict[str, Any], planned_tasks: list[dict[str, Any]]) -> None:
        self.state["run"] = run_info
        previous_tasks = self.state.get("tasks", {})
        planned_ids = {task["task_id"] for task in planned_tasks}
        archived = self.state.setdefault("archived_tasks", {})
        for task_id, task in previous_tasks.items():
            if task_id not in planned_ids:
                archived[task_id] = {
                    **task,
                    "archived_at": utc_now(),
                    "archive_reason": "not_in_current_plan",
                }
        tasks: dict[str, Any] = {}
        for task in planned_tasks:
            task_id = task["task_id"]
            previous = previous_tasks.get(task_id, {})
            runtime = {
                key: value
                for key, value in previous.items()
                if key
                in {
                    "status",
                    "attempts",
                    "request_ids",
                    "last_error",
                    "http_status",
                    "started_at",
                    "completed_at",
                    "elapsed_seconds",
                    "response",
                    "output_size",
                }
            }
            tasks[task_id] = {**task, "status": "pending", "attempts": 0, "request_ids": [], **runtime}
        self.state["tasks"] = tasks
        self.save()

    def task(self, task_id: str) -> dict[str, Any]:
        return self.state["tasks"][task_id]

    def mark(self, task_id: str, status: str, **updates: Any) -> None:
        task = self.task(task_id)
        task.update(updates)
        task["status"] = status
        if status == "submitted" and not task.get("started_at"):
            task["started_at"] = utc_now()
        if status in TERMINAL_STATUSES:
            task["completed_at"] = utc_now()
        self.append_event({"time": utc_now(), "task_id": task_id, "status": status, **updates})
        self.save()

    def add_request(self, task_id: str, request_id: str) -> int:
        task = self.task(task_id)
        request_ids = task.setdefault("request_ids", [])
        attempt = max(task.get("attempts", 0), len(request_ids)) + 1
        task["attempts"] = attempt
        request_ids.append(request_id)
        self.mark(task_id, "submitted", request_id=request_id, attempt=attempt)
        return attempt

    def append_event(self, event: dict[str, Any]) -> None:
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8") as output:
            output.write(json.dumps(event, ensure_ascii=False) + "\n")
            output.flush()
            os.fsync(output.fileno())

    def save(self) -> None:
        self.state["updated_at"] = utc_now()
        atomic_write_json(self.checkpoint_path, self.state)

    def counts(self, task_ids: Optional[list[str]] = None) -> dict[str, int]:
        counts: dict[str, int] = {}
        selected = task_ids or list(self.state.get("tasks", {}))
        for task_id in selected:
            status = self.task(task_id).get("status", "pending")
            counts[status] = counts.get(status, 0) + 1
        return counts
