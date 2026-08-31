from __future__ import annotations

import json

from subject_recolor.cli import main
from subject_recolor.planner import build_tasks
from subject_recolor.review import build_review


def test_cli_uses_job_config(job_dir) -> None:
    workspace = job_dir.parent
    assert main(["--workspace", str(workspace), "--latest"]) == 0


def test_run_guard(job_dir) -> None:
    workspace = job_dir.parent
    code = main(["run", "--workspace", str(workspace), "--latest"])
    assert code == 2


def test_expect_calls_guard(job_dir) -> None:
    workspace = job_dir.parent
    code = main(
        [
            "run",
            "--workspace",
            str(workspace),
            "--latest",
            "--expect-calls",
            "99",
            "--yes",
        ]
    )
    assert code == 2


def test_max_paid_calls_guard(job_dir) -> None:
    workspace = job_dir.parent
    code = main(
        [
            "run",
            "--workspace",
            str(workspace),
            "--latest",
            "--max-paid-calls",
            "0",
            "--yes",
        ]
    )
    assert code == 2


def test_json_plan(job_dir, capsys) -> None:
    workspace = job_dir.parent
    code = main(["plan", "--workspace", str(workspace), "--latest", "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["job"] == job_dir.name
    assert payload["inputs"] == ["scene"]
    assert payload["color_cards"] == ["navy"]
    assert payload["new_calls"] == 1


def test_init_creates_job(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    code = main(
        [
            "init",
            "--workspace",
            str(workspace),
            "--date",
            "2026-09-02",
            "--subject",
            "雨伞",
        ]
    )
    assert code == 0
    assert (workspace / "2026-09-02" / "job.toml").is_file()


def test_review_page_is_triptych(job_dir) -> None:
    tasks = build_tasks(job_dir, "沙发", "gpt-image-2")
    page = build_review(tasks, job_dir)
    text = page.read_text(encoding="utf-8")
    assert "指定主体换色审阅" in text
    assert "原图" in text
    assert "色卡" in text
    assert "换色结果" in text
    assert "navy.png" in text


def test_offline_demo(tmp_path) -> None:
    workspace = tmp_path / "demo"
    assert main(["demo", "--workspace", str(workspace)]) == 0
    output = workspace / "2026-01-15" / "output"
    assert (output / "review.html").is_file()
    assert len(list((output / "png").glob("*.png"))) == 2
