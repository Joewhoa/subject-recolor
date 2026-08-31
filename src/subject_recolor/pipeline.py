from __future__ import annotations

import json
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from .artifacts import repair_jpg, save_png_and_jpg, valid_image
from .gateway import GatewayError, GatewayUncertain, ImageEditGateway
from .models import RecolorTask
from .provenance import source_record
from .utils import append_jsonl, atomic_write_json, sha256_file, utc_now


def _load_metadata(task: RecolorTask) -> dict[str, Any] | None:
    try:
        with task.metadata_path.open(encoding="utf-8") as stream:
            data = json.load(stream)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _metadata_matches(task: RecolorTask, require_jpg: bool) -> bool:
    metadata = _load_metadata(task)
    if metadata is None or metadata.get("task_id") != task.task_id:
        return False
    if not valid_image(task.png_path):
        return False
    if metadata.get("png_sha256") != sha256_file(task.png_path):
        return False
    if require_jpg:
        if not valid_image(task.jpg_path):
            return False
        if metadata.get("jpg_sha256") != sha256_file(task.jpg_path):
            return False
    return True


def _write_metadata(
    task: RecolorTask,
    job_dir: Path,
    request_id: str | None,
    response: dict[str, Any],
) -> None:
    provenance = source_record(task, job_dir)
    atomic_write_json(
        task.metadata_path,
        {
            **task.to_dict(),
            "status": "succeeded",
            "request_id": request_id,
            "png_sha256": sha256_file(task.png_path),
            "jpg_sha256": sha256_file(task.jpg_path),
            "response": response,
            "source_provenance": provenance,
            "completed_at": utc_now(),
        },
    )


def classify_task(task: RecolorTask) -> str:
    if _metadata_matches(task, require_jpg=True):
        return "complete"
    if _metadata_matches(task, require_jpg=False):
        return "repair_jpg"
    return "new_call"


def summarize_plan(tasks: list[RecolorTask]) -> dict[str, int]:
    counts = Counter(classify_task(task) for task in tasks)
    return {
        "tasks": len(tasks),
        "complete": counts["complete"],
        "repair_jpg": counts["repair_jpg"],
        "new_calls": counts["new_call"],
        "expected_png": len(tasks),
        "expected_jpg": len(tasks),
    }


def execute_tasks(
    tasks: list[RecolorTask],
    gateway: ImageEditGateway,
    job_dir: Path,
) -> tuple[list[dict[str, Any]], bool]:
    output = job_dir / "output"
    log_path = output / "run.jsonl"
    initial_plan = summarize_plan(tasks)
    results: list[dict[str, Any]] = []
    halted = False

    for task in tasks:
        state = classify_task(task)
        if state == "complete":
            results.append({"task_id": task.task_id, "status": "succeeded", "cached": True})
            continue
        if state == "repair_jpg":
            metadata = _load_metadata(task) or {}
            repair_jpg(task.png_path, task.jpg_path)
            _write_metadata(
                task,
                job_dir,
                metadata.get("request_id"),
                metadata.get("response", {}),
            )
            results.append({"task_id": task.task_id, "status": "succeeded", "repaired_jpg": True})
            continue

        request_id = str(uuid.uuid4())
        append_jsonl(
            log_path,
            {
                "time": utc_now(),
                "task_id": task.task_id,
                "status": "submitted",
                "request_id": request_id,
                "source_sha256": task.source_sha256,
                "color_card_sha256": task.color_card_sha256,
                "model": task.model,
                "profile": task.profile,
            },
        )
        try:
            edit = gateway.edit(task.source, task.prompt, task.model, request_id)
            sizes = save_png_and_jpg(edit.png, task.source, task.png_path, task.jpg_path)
            _write_metadata(task, job_dir, request_id, edit.response)
            record = {
                "time": utc_now(),
                "task_id": task.task_id,
                "status": "succeeded",
                "request_id": request_id,
                "png": task.png_path.relative_to(job_dir).as_posix(),
                "jpg": task.jpg_path.relative_to(job_dir).as_posix(),
                "metadata": task.metadata_path.relative_to(job_dir).as_posix(),
                **sizes,
                "response": edit.response,
            }
        except GatewayUncertain as exc:
            record = {
                "time": utc_now(),
                "task_id": task.task_id,
                "status": "uncertain",
                "request_id": request_id,
                "error": str(exc),
            }
            halted = True
        except GatewayError as exc:
            rejected = exc.status_code in {400, 401, 403}
            record = {
                "time": utc_now(),
                "task_id": task.task_id,
                "status": "rejected" if rejected else "failed_safe",
                "request_id": request_id,
                "http_status": exc.status_code,
                "error": str(exc),
            }
            halted = rejected
        except (OSError, ValueError) as exc:
            record = {
                "time": utc_now(),
                "task_id": task.task_id,
                "status": "failed_safe",
                "request_id": request_id,
                "error": f"artifact validation failed: {exc}",
            }
        append_jsonl(log_path, record)
        results.append(record)
        if halted:
            break

    report = {
        "created_at": utc_now(),
        "halted": halted,
        "plan": initial_plan,
        "final_state": summarize_plan(tasks),
        "results": results,
    }
    atomic_write_json(output / "run-report.json", report)
    return results, halted
