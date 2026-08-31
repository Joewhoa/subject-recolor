from __future__ import annotations

import colorsys
import math
from pathlib import Path

from PIL import Image, ImageOps, ImageStat

from .models import ColorSample


def describe_color(rgb: tuple[int, int, int]) -> str:
    red, green, blue = (value / 255 for value in rgb)
    hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)
    if saturation < 0.08:
        if value < 0.18:
            return "接近黑色的深灰"
        if value < 0.40:
            return "深灰色"
        if value < 0.68:
            return "中性灰色"
        if value < 0.88:
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
        name = "低饱和的" + name
    elif saturation > 0.65:
        name = "高饱和的" + name
    if value < 0.32:
        name = "深" + name
    elif value > 0.82:
        name = "浅" + name
    return name


def sample_center_mean(path: Path, crop_size: int = 200) -> ColorSample:
    """Use the validated baseline: arithmetic mean of the centered square in sRGB."""
    if crop_size <= 0:
        raise ValueError("crop_size must be positive")
    with Image.open(path) as raw:
        image = ImageOps.exif_transpose(raw).convert("RGB")
        width, height = image.size
        crop_width = min(crop_size, width)
        crop_height = min(crop_size, height)
        left = (width - crop_width) // 2
        top = (height - crop_height) // 2
        crop = image.crop((left, top, left + crop_width, top + crop_height))
        stat = ImageStat.Stat(crop)
    rgb = tuple(int(round(channel)) for channel in stat.mean[:3])
    stddev = tuple(round(math.sqrt(value), 2) for value in stat.var[:3])
    return ColorSample(
        rgb=rgb,
        hex=f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}",
        label=describe_color(rgb),
        stddev=stddev,
        crop_size=(crop_width, crop_height),
    )
