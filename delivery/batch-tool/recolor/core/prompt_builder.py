"""Color extraction and versioned recoloring prompts."""

from __future__ import annotations

import colorsys
from pathlib import Path
from typing import Any

from PIL import Image, ImageStat

PROMPT_VERSION = "field-recolor-v3-20260903"


def color_description(rgb: tuple[int, int, int]) -> str:
    red, green, blue = (value / 255 for value in rgb)
    hue, saturation, brightness = colorsys.rgb_to_hsv(red, green, blue)
    if saturation < 0.08:
        if brightness < 0.18:
            return "接近黑色的深灰"
        if brightness < 0.40:
            return "深灰色"
        if brightness < 0.68:
            return "中性灰色"
        if brightness < 0.88:
            return "浅灰色"
        return "接近白色的亮灰"

    degree = hue * 360
    if degree < 15 or degree >= 345:
        name = "红色"
    elif degree < 40:
        name = "橙棕色"
    elif degree < 65:
        name = "暖黄色"
    elif degree < 155:
        name = "绿色"
    elif degree < 190:
        name = "青绿色"
    elif degree < 225:
        name = "蓝青色"
    elif degree < 260:
        name = "蓝色"
    elif degree < 300:
        name = "紫色"
    else:
        name = "紫红色"
    if saturation < 0.25:
        name = f"低饱和的{name}"
    elif saturation > 0.65:
        name = f"高饱和的{name}"
    if brightness < 0.32:
        name = f"深{name}"
    elif brightness > 0.82:
        name = f"浅{name}"
    return name


def extract_color(card_path: Path) -> dict[str, Any]:
    """Average the exact center 200x200 crop used by the successful handoff run."""

    with Image.open(card_path) as source:
        image = source.convert("RGB")
        width, height = image.size
        half = 100
        crop = image.crop(
            (
                max(0, width // 2 - half),
                max(0, height // 2 - half),
                min(width, width // 2 + half),
                min(height, height // 2 + half),
            )
        )
        mean = ImageStat.Stat(crop).mean
    rgb = tuple(int(round(channel)) for channel in mean)
    return {
        "rgb": list(rgb),
        "hex": "#%02X%02X%02X" % rgb,
        "description": color_description(rgb),
        "sample": "center_200x200_mean",
    }


def build_prompt(subject: str, color: dict[str, Any], profile: str = "B") -> str:
    profile = profile.upper()
    if profile not in {"A", "B"}:
        raise ValueError("profile 只能是 A 或 B")
    red, green, blue = color["rgb"]
    if profile == "A":
        return (
            f"将{subject}布料颜色改为{color['description']}（HEX {color['hex']}，约 RGB {red},{green},{blue}）。"
            f"保持{subject}布料的褶皱、纹理、光影与垂坠感，只改变{subject}颜色，"
            "背景、窗户、墙面、植物和其他非目标对象保持原样。"
        )
    tone_guard = ""
    if max(red, green, blue) < 80:
        tone_guard = "目标色较深，不得压成死黑，必须保留全部褶皱、阴影层次和织物细节。"
    elif min(red, green, blue) > 190:
        tone_guard = "目标色较浅，不得过曝成纯白，必须保留高光层次和织物细节。"
    elif max(red, green, blue) - min(red, green, blue) > 100:
        tone_guard = "目标色饱和度较高，颜色不得溢出或污染主体边缘以外的背景。"

    return (
        f"将图片中所有可见的{subject}布料颜色改为{color['description']}，"
        f"目标基础色为 HEX {color['hex']}（约 RGB {red},{green},{blue}）。"
        f"必须完整识别并更换画面中每一组、每一片{subject}，包括远处、阴影中和被部分遮挡的部分。"
        f"保持{subject}原有材质、织物纹理、褶皱、垂坠、透光性、挂孔结构、轮廓、位置、尺寸、"
        "高光、环境光和阴影关系；目标颜色应随原有光照自然变化，而不是将布料涂成单一色块。"
        "背景、木质结构、窗帘杆、挂环、墙面、地面、建筑、沙发、靠垫、桌椅、花盆、植物、"
        "泳池和其他所有元素一律保持原样。不得增加、删除、移动、重绘或重新设计任何元素，"
        "不得改变构图、视角、景深、清晰度和宽高比例。"
        f"{tone_guard}只输出完成换色后的照片，不添加文字、标签、边框或水印。"
    )
