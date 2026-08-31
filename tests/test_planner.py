from __future__ import annotations

import pytest
from PIL import Image

from subject_recolor.planner import build_tasks, discover_jobs, resolve_job


def test_discovery_and_stable_task_id(job_dir) -> None:
    workspace = job_dir.parent
    assert discover_jobs(workspace) == [job_dir]
    assert resolve_job(workspace, None, True) == job_dir
    first = build_tasks(job_dir, "沙发", "gpt-image-2")
    second = build_tasks(job_dir, "沙发", "gpt-image-2")
    assert len(first) == 1
    assert first[0].task_id == second[0].task_id
    assert first[0].profile == "enhanced-v1"


def test_subject_changes_content_identity(job_dir) -> None:
    sofa = build_tasks(job_dir, "沙发", "gpt-image-2")[0]
    umbrella = build_tasks(job_dir, "雨伞", "gpt-image-2")[0]
    assert sofa.task_id != umbrella.task_id


def test_duplicate_stems_are_rejected(job_dir) -> None:
    Image.new("RGB", (64, 64), "white").save(job_dir / "input" / "scene.jpg")
    with pytest.raises(ValueError, match="duplicate input stems"):
        build_tasks(job_dir, "沙发", "gpt-image-2")


def test_input_filter(job_dir) -> None:
    tasks = build_tasks(
        job_dir,
        "沙发",
        "gpt-image-2",
        selected_inputs={"scene"},
        selected_cards={"navy"},
    )
    assert len(tasks) == 1
