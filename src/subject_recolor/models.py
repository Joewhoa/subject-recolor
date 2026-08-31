from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

TaskStatus = Literal[
    "planned",
    "submitted",
    "succeeded",
    "failed_safe",
    "uncertain",
    "rejected",
]


@dataclass(frozen=True)
class ColorSample:
    rgb: tuple[int, int, int]
    hex: str
    label: str
    stddev: tuple[float, float, float]
    crop_size: tuple[int, int]
    method: str = "center-mean-v1"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["rgb"] = list(self.rgb)
        data["stddev"] = list(self.stddev)
        data["crop_size"] = list(self.crop_size)
        return data


@dataclass(frozen=True)
class RecolorTask:
    task_id: str
    source: Path
    color_card: Path
    source_sha256: str
    color_card_sha256: str
    color: ColorSample
    subject: str
    profile: str
    prompt: str
    model: str
    png_path: Path
    jpg_path: Path
    metadata_path: Path

    def to_dict(self, root: Path | None = None) -> dict[str, Any]:
        def display(path: Path) -> str:
            if root is not None:
                try:
                    return path.relative_to(root).as_posix()
                except ValueError:
                    pass
            return str(path)

        return {
            "task_id": self.task_id,
            "source": display(self.source),
            "color_card": display(self.color_card),
            "source_sha256": self.source_sha256,
            "color_card_sha256": self.color_card_sha256,
            "color": self.color.to_dict(),
            "subject": self.subject,
            "profile": self.profile,
            "prompt": self.prompt,
            "model": self.model,
            "png": display(self.png_path),
            "jpg": display(self.jpg_path),
            "metadata": display(self.metadata_path),
        }


@dataclass(frozen=True)
class EditResult:
    png: bytes
    response: dict[str, Any]
