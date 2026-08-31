from __future__ import annotations

import io
import re
from pathlib import Path

from PIL import Image, ImageDraw

from .models import EditResult

HEX_PATTERN = re.compile(r"HEX (#[0-9A-Fa-f]{6})")


def create_demo_job(workspace: Path, date: str = "2026-01-15") -> Path:
    job = workspace / date
    inputs = job / "input"
    cards = job / "color_cards"
    inputs.mkdir(parents=True, exist_ok=True)
    cards.mkdir(parents=True, exist_ok=True)
    (job / "job.toml").write_text(
        'subject = "沙发"\nmodel = "offline-demo"\ncolor_crop_size = 200\n',
        encoding="utf-8",
    )
    scene = Image.new("RGB", (512, 512), "#dbeafe")
    draw = ImageDraw.Draw(scene)
    draw.rectangle((0, 330, 512, 512), fill="#d1d5db")
    draw.rounded_rectangle(
        (105, 205, 407, 375), radius=36, fill="#8b5e3c", outline="#4b3621", width=8
    )
    draw.rectangle((135, 160, 377, 265), fill="#a47148", outline="#4b3621", width=8)
    draw.line((175, 165, 175, 365), fill="#6b4423", width=5)
    draw.line((337, 165, 337, 365), fill="#6b4423", width=5)
    scene.save(inputs / "synthetic_sofa.png")
    for name, color in {"navy": "#182B3A", "teal": "#60A8AD"}.items():
        Image.new("RGB", (400, 400), color).save(cards / f"{name}.png")
    return job


class OfflineDemoGateway:
    """Deterministic synthetic-only adapter; it is not a generative model."""

    def edit(self, source: Path, prompt: str, model: str, request_id: str) -> EditResult:
        match = HEX_PATTERN.search(prompt)
        if not match:
            raise ValueError("demo prompt has no HEX target")
        target = tuple(bytes.fromhex(match.group(1)[1:]))
        with Image.open(source) as raw:
            image = raw.convert("RGB")
            pixels = image.load()
            for y in range(image.height):
                for x in range(image.width):
                    red, green, blue = pixels[x, y]
                    if red > green > blue and red - blue > 25:
                        luminance = (red + green + blue) / (3 * 128)
                        pixels[x, y] = tuple(
                            max(0, min(255, round(channel * luminance))) for channel in target
                        )
            buffer = io.BytesIO()
            image.save(buffer, "PNG")
        return EditResult(
            png=buffer.getvalue(),
            response={"model": "offline-demo", "note": "deterministic synthetic demo"},
        )
