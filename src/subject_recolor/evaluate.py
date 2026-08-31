from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageOps, ImageStat

from .artifacts import valid_image
from .models import RecolorTask
from .pipeline import classify_task


def structural_metrics(source_path: Path, result_path: Path) -> dict[str, Any]:
    """Compute mask-free diagnostics; these do not determine semantic correctness."""
    with Image.open(source_path) as source_raw, Image.open(result_path) as result_raw:
        source = ImageOps.exif_transpose(source_raw).convert("RGB")
        result = ImageOps.exif_transpose(result_raw).convert("RGB")
        source_ratio = source.width / source.height
        result_ratio = result.width / result.height
        ratio_difference = abs(source_ratio - result_ratio)
        original_result_size = result.size
        same_dimensions = source.size == original_result_size
        if ratio_difference > 0.01:
            return {
                "source_size": list(source.size),
                "result_size": list(original_result_size),
                "same_dimensions": same_dimensions,
                "aspect_ratio_preserved": False,
                "aspect_ratio_difference": round(ratio_difference, 6),
            }
        if not same_dimensions:
            result = result.resize(source.size, Image.Resampling.LANCZOS)
        difference = ImageChops.difference(source, result)
        gray = difference.convert("L")
        stat = ImageStat.Stat(gray)
        histogram = gray.histogram()
        total = source.width * source.height
        changed = total - sum(histogram[:9])
        major_changed = total - sum(histogram[:33])
        return {
            "source_size": list(source.size),
            "result_size": list(original_result_size),
            "same_dimensions": same_dimensions,
            "aspect_ratio_preserved": True,
            "aspect_ratio_difference": round(ratio_difference, 6),
            "comparison_resized_to_source": not same_dimensions,
            "mean_absolute_luma_difference": round(stat.mean[0], 3),
            "changed_pixel_ratio_threshold_8": round(changed / total, 6),
            "changed_pixel_ratio_threshold_32": round(major_changed / total, 6),
            "warning": (
                "Mask-free metrics measure global change only; they cannot distinguish "
                "correct subject edits from background drift."
            ),
        }


def evaluate_tasks(tasks: list[RecolorTask], job_dir: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for task in tasks:
        record: dict[str, Any] = {
            "task_id": task.task_id,
            "source": task.source.relative_to(job_dir).as_posix(),
            "result": task.png_path.relative_to(job_dir).as_posix(),
            "cache_state": classify_task(task),
            "artifact_valid": valid_image(task.png_path),
        }
        if record["artifact_valid"]:
            record["structural_metrics"] = structural_metrics(task.source, task.png_path)
        records.append(record)
    return {
        "job": job_dir.name,
        "evaluated": len(records),
        "results_available": sum(item["artifact_valid"] for item in records),
        "manual_review_required": True,
        "records": records,
    }
