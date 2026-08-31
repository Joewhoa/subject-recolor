from __future__ import annotations

from .models import ColorSample

PROMPT_VERSION = "enhanced-v1"


def build_prompt(subject: str, color: ColorSample) -> str:
    """Build the single retained production prompt (the former B profile)."""
    subject = subject.strip()
    if not subject:
        raise ValueError("subject cannot be empty")
    red, green, blue = color.rgb
    detail = ""
    if max(color.rgb) < 80:
        detail = "目标色较深，不得压成死黑，必须保留阴影层次、表面纹理和结构细节。"
    elif min(color.rgb) > 190:
        detail = "目标色较浅，不得过曝成纯白，必须保留高光层次、表面纹理和结构细节。"
    return (
        f"将图片中所有可见的“{subject}”颜色改为{color.label}。"
        f"以 HEX {color.hex}（约 RGB {red},{green},{blue}）为目标颜色基准，"
        "自然语言颜色名称仅用于辅助理解。"
        f"必须完整识别并更换画面中的每一个“{subject}”实例，包括远处、阴影中、"
        "被部分遮挡的区域。保持主体原有材质及其表面纹理、褶皱或结构细节、轮廓、"
        "位置、尺寸、透明或反光特性、高光、环境光和阴影关系，只改变指定主体颜色。"
        "除指定主体外，背景、建筑、墙面、地面、家具、植物、人物、配件及其他所有"
        "元素一律保持原样。不得增加、删除、移动或重新设计任何元素，不得改变构图、"
        f"视角、景深和宽高比例。{detail}"
    )
