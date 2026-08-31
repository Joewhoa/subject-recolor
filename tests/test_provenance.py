from __future__ import annotations

import json

from subject_recolor.models import EditResult
from subject_recolor.pipeline import execute_tasks
from subject_recolor.planner import build_tasks
from subject_recolor.review import build_review


class FakeGateway:
    def __init__(self, png: bytes) -> None:
        self.png = png

    def edit(self, source, prompt, model, request_id):
        return EditResult(self.png, {"model": model})


def _write_sources(job_dir) -> None:
    payload = {
        "sources": [
            {
                "local_file": f"workspace/{job_dir.name}/input/scene.png",
                "title": "Public sofa",
                "creator": "Example Author",
                "source_page": "https://example.test/source",
                "license": "CC BY 4.0",
                "license_url": "https://creativecommons.org/licenses/by/4.0/",
            }
        ]
    }
    (job_dir.parent.parent / "SOURCES.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_provenance_enters_metadata_and_review(job_dir, png_bytes) -> None:
    _write_sources(job_dir)
    tasks = build_tasks(job_dir, "沙发", "gpt-image-2")
    execute_tasks(tasks, FakeGateway(png_bytes), job_dir)
    metadata = json.loads(tasks[0].metadata_path.read_text(encoding="utf-8"))
    assert metadata["source_provenance"]["creator"] == "Example Author"
    review = build_review(tasks, job_dir).read_text(encoding="utf-8")
    assert "Public sofa" in review
    assert "CC BY 4.0" in review
    assert "本图结果为修改版本" in review
