from __future__ import annotations

from pathlib import Path

from PIL import Image

from subject_recolor.color import sample_center_mean
from subject_recolor.prompt import build_prompt


def test_center_mean_and_generic_subject(tmp_path: Path) -> None:
    card = tmp_path / "card.png"
    Image.new("RGB", (300, 300), (24, 43, 58)).save(card)
    color = sample_center_mean(card)
    assert color.rgb == (24, 43, 58)
    assert color.hex == "#182B3A"
    assert color.stddev == (0.0, 0.0, 0.0)
    prompt = build_prompt("沙发", color)
    assert "沙发" in prompt
    assert "#182B3A" in prompt
    assert "除指定主体外" in prompt
    assert "窗帘杆" not in prompt
