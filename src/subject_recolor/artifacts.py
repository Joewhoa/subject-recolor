from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

from .utils import atomic_write


def valid_image(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            image.verify()
        return path.stat().st_size > 0
    except (OSError, UnidentifiedImageError):
        return False


def save_png_and_jpg(
    png_bytes: bytes,
    source_path: Path,
    png_path: Path,
    jpg_path: Path,
) -> dict[str, Any]:
    """Preserve exact PNG bytes and atomically derive a progressive JPEG."""
    with Image.open(io.BytesIO(png_bytes)) as generated:
        generated.load()
        if generated.format != "PNG":
            raise ValueError(f"expected PNG response, received {generated.format!r}")
        generated_size = generated.size
        with Image.open(source_path) as source_raw:
            source = ImageOps.exif_transpose(source_raw)
            source_size = source.size
        source_ratio = source_size[0] / source_size[1]
        generated_ratio = generated_size[0] / generated_size[1]
        if abs(source_ratio - generated_ratio) > 0.01:
            raise ValueError(
                f"aspect ratio changed: source={source_size}, generated={generated_size}"
            )
        buffer = io.BytesIO()
        generated.convert("RGB").save(
            buffer,
            "JPEG",
            quality=85,
            progressive=True,
            optimize=True,
            subsampling="4:2:0",
        )
    atomic_write(png_path, png_bytes)
    atomic_write(jpg_path, buffer.getvalue())
    return {
        "source_size": list(source_size),
        "generated_size": list(generated_size),
    }


def repair_jpg(png_path: Path, jpg_path: Path) -> None:
    with Image.open(png_path) as image:
        image.load()
        buffer = io.BytesIO()
        image.convert("RGB").save(
            buffer,
            "JPEG",
            quality=85,
            progressive=True,
            optimize=True,
            subsampling="4:2:0",
        )
    atomic_write(jpg_path, buffer.getvalue())
