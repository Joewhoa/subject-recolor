from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture
def job_dir(tmp_path: Path) -> Path:
    job = tmp_path / "workspace" / "2026-01-15"
    (job / "input").mkdir(parents=True)
    (job / "color_cards").mkdir()
    Image.new("RGB", (64, 64), "#777777").save(job / "input" / "scene.png")
    Image.new("RGB", (64, 64), "#182B3A").save(job / "color_cards" / "navy.png")
    (job / "job.toml").write_text(
        'subject = "沙发"\nmodel = "gpt-image-2"\ncolor_crop_size = 200\n',
        encoding="utf-8",
    )
    return job


@pytest.fixture
def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), "#182B3A").save(buffer, "PNG")
    return buffer.getvalue()
