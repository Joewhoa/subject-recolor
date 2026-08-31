from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    parser = argparse.ArgumentParser(description="Create synthetic inputs for an offline demo")
    parser.add_argument("--workspace", type=Path, default=Path("workspace"))
    parser.add_argument("--date", default="2026-01-15")
    args = parser.parse_args()

    job = args.workspace / args.date
    inputs = job / "input"
    cards = job / "color_cards"
    inputs.mkdir(parents=True, exist_ok=True)
    cards.mkdir(parents=True, exist_ok=True)
    (job / "job.toml").write_text(
        'subject = "沙发"\nmodel = "gpt-image-2"\ncolor_crop_size = 200\n',
        encoding="utf-8",
    )

    scene = Image.new("RGB", (512, 512), "#dbeafe")
    draw = ImageDraw.Draw(scene)
    draw.rectangle((0, 330, 512, 512), fill="#d1d5db")
    draw.rounded_rectangle(
        (105, 205, 407, 375),
        radius=36,
        fill="#8b5e3c",
        outline="#4b3621",
        width=8,
    )
    draw.rectangle((135, 160, 377, 265), fill="#a47148", outline="#4b3621", width=8)
    draw.line((175, 165, 175, 365), fill="#6b4423", width=5)
    draw.line((337, 165, 337, 365), fill="#6b4423", width=5)
    scene.save(inputs / "synthetic_sofa.png")

    for name, color in {"navy": "#182B3A", "teal": "#60A8AD"}.items():
        card = Image.new("RGB", (400, 400), color)
        card.save(cards / f"{name}.png")
    print(job)


if __name__ == "__main__":
    main()
