from __future__ import annotations

import json

from subject_recolor.artifacts import save_png_and_jpg, valid_image
from subject_recolor.gateway import GatewayUncertain
from subject_recolor.models import EditResult
from subject_recolor.pipeline import classify_task, execute_tasks
from subject_recolor.planner import build_tasks


class FakeGateway:
    def __init__(self, png: bytes) -> None:
        self.png = png
        self.calls = 0

    def edit(self, source, prompt, model, request_id):
        self.calls += 1
        return EditResult(self.png, {"model": model})


class InvalidArtifactGateway:
    def edit(self, source, prompt, model, request_id):
        return EditResult(b"not-a-png", {})


class UnknownGateway:
    def __init__(self) -> None:
        self.calls = 0

    def edit(self, source, prompt, model, request_id):
        self.calls += 1
        raise GatewayUncertain("timeout outcome unknown")


def test_preserve_png_and_derive_jpg(job_dir, png_bytes) -> None:
    png = job_dir / "output" / "png" / "x.png"
    jpg = job_dir / "output" / "jpg" / "x.jpg"
    save_png_and_jpg(png_bytes, job_dir / "input" / "scene.png", png, jpg)
    assert png.read_bytes() == png_bytes
    assert valid_image(jpg)


def test_successful_pipeline_and_cache(job_dir, png_bytes) -> None:
    tasks = build_tasks(job_dir, "沙发", "gpt-image-2")
    gateway = FakeGateway(png_bytes)
    results, halted = execute_tasks(tasks, gateway, job_dir)
    assert not halted
    assert results[0]["status"] == "succeeded"
    assert gateway.calls == 1
    first_report = json.loads(
        (job_dir / "output" / "run-report.json").read_text(encoding="utf-8")
    )
    assert first_report["plan"]["new_calls"] == 1
    assert first_report["final_state"]["complete"] == 1
    execute_tasks(tasks, gateway, job_dir)
    assert gateway.calls == 1
    assert tasks[0].metadata_path.is_file()
    cached_report = json.loads(
        (job_dir / "output" / "run-report.json").read_text(encoding="utf-8")
    )
    assert cached_report["plan"]["new_calls"] == 0


def test_cache_rejects_changed_task_identity(job_dir, png_bytes) -> None:
    original = build_tasks(job_dir, "沙发", "gpt-image-2")
    gateway = FakeGateway(png_bytes)
    execute_tasks(original, gateway, job_dir)
    changed = build_tasks(job_dir, "雨伞", "gpt-image-2")
    assert classify_task(changed[0]) == "new_call"


def test_invalid_artifact_is_recorded_as_failed_safe(job_dir) -> None:
    tasks = build_tasks(job_dir, "沙发", "gpt-image-2")
    results, halted = execute_tasks(tasks, InvalidArtifactGateway(), job_dir)
    assert not halted
    assert results[0]["status"] == "failed_safe"
    assert "artifact validation failed" in results[0]["error"]
    assert (job_dir / "output" / "run-report.json").is_file()


def test_uncertain_halts_remaining_tasks(job_dir) -> None:
    from PIL import Image

    Image.new("RGB", (64, 64), "#60A8AD").save(job_dir / "color_cards" / "teal.png")
    tasks = build_tasks(job_dir, "沙发", "gpt-image-2")
    gateway = UnknownGateway()
    results, halted = execute_tasks(tasks, gateway, job_dir)
    assert halted
    assert gateway.calls == 1
    assert len(results) == 1
    assert results[0]["status"] == "uncertain"
