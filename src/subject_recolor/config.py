from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .utils import atomic_write

DATE_PATTERN = re.compile(r"(?:\d{4}|\d{8}|\d{4}-\d{2}-\d{2})$")


@dataclass(frozen=True)
class JobConfig:
    subject: str
    model: str = "gpt-image-2"
    color_crop_size: int = 200


def load_job_config(job_dir: Path) -> JobConfig:
    path = job_dir / "job.toml"
    if not path.is_file():
        raise ValueError(f"missing job config: {path}")
    with path.open("rb") as stream:
        raw = tomllib.load(stream)
    subject = str(raw.get("subject", "")).strip()
    model = str(raw.get("model", "gpt-image-2")).strip()
    crop_size = int(raw.get("color_crop_size", 200))
    if not subject:
        raise ValueError(f"job subject is empty: {path}")
    if not model:
        raise ValueError(f"job model is empty: {path}")
    if crop_size <= 0:
        raise ValueError("color_crop_size must be positive")
    return JobConfig(subject=subject, model=model, color_crop_size=crop_size)


def create_job(workspace: Path, date: str, subject: str, model: str) -> Path:
    if not DATE_PATTERN.fullmatch(date):
        raise ValueError("date must be MMDD, YYYYMMDD, or YYYY-MM-DD")
    subject = subject.strip()
    model = model.strip()
    if not subject or not model:
        raise ValueError("subject and model cannot be empty")
    job_dir = workspace / date
    config_path = job_dir / "job.toml"
    if config_path.exists():
        raise FileExistsError(f"job already exists: {job_dir}")
    (job_dir / "input").mkdir(parents=True, exist_ok=True)
    (job_dir / "color_cards").mkdir(parents=True, exist_ok=True)
    content = (
        f'subject = "{subject.replace(chr(34), chr(92) + chr(34))}"\n'
        f'model = "{model.replace(chr(34), chr(92) + chr(34))}"\n'
        "color_crop_size = 200\n"
    )
    atomic_write(config_path, content.encode("utf-8"))
    return job_dir
