from __future__ import annotations

from PIL import Image

from subject_recolor.evaluate import evaluate_tasks, structural_metrics
from subject_recolor.planner import build_tasks


def test_structural_metrics_identical_and_changed(tmp_path) -> None:
    source = tmp_path / "source.png"
    same = tmp_path / "same.png"
    changed = tmp_path / "changed.png"
    Image.new("RGB", (32, 32), "black").save(source)
    Image.new("RGB", (32, 32), "black").save(same)
    Image.new("RGB", (32, 32), "white").save(changed)
    identical = structural_metrics(source, same)
    assert identical["same_dimensions"]
    assert identical["changed_pixel_ratio_threshold_8"] == 0
    different = structural_metrics(source, changed)
    assert different["changed_pixel_ratio_threshold_32"] == 1


def test_structural_metrics_resizes_same_ratio(tmp_path) -> None:
    source = tmp_path / "source.png"
    result = tmp_path / "result.png"
    Image.new("RGB", (32, 16), "black").save(source)
    Image.new("RGB", (64, 32), "white").save(result)
    metrics = structural_metrics(source, result)
    assert not metrics["same_dimensions"]
    assert metrics["aspect_ratio_preserved"]
    assert metrics["comparison_resized_to_source"]
    assert metrics["changed_pixel_ratio_threshold_32"] == 1


def test_evaluate_missing_result(job_dir) -> None:
    tasks = build_tasks(job_dir, "沙发", "gpt-image-2")
    report = evaluate_tasks(tasks, job_dir)
    assert report["evaluated"] == 1
    assert report["results_available"] == 0
    assert report["manual_review_required"] is True
