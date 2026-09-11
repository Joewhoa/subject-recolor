"""Safe filesystem helpers used by the batch pipeline."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, UnidentifiedImageError

SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def list_images(folder: Path) -> list[Path]:
    if not folder.is_dir():
        raise FileNotFoundError(f"缺少目录：{folder}")
    paths = [
        path
        for path in folder.iterdir()
        if path.is_file()
        and not path.name.startswith((".", "~$"))
        and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
    ]
    return sorted(paths, key=lambda item: item.name.casefold())


def validate_input_image(path: Path) -> tuple[int, int]:
    try:
        with Image.open(path) as image:
            image.load()
            if image.width < 32 or image.height < 32:
                raise ValueError(f"图片尺寸过小：{path.name} ({image.width}x{image.height})")
            return image.size
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError(f"无法解码图片：{path}") from exc


def valid_output_image(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except (OSError, UnidentifiedImageError):
        return False


def safe_name(text: str) -> str:
    invalid = '<>:"/\\|?*\0'
    cleaned = "".join("_" if char in invalid else char for char in text).strip().rstrip(".")
    return cleaned or "unnamed"


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(parts: Iterable[str], length: int = 20) -> str:
    payload = "\0".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:length]


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".part", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_json(path: Path, data: Any) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def clean_dragged_path(value: str) -> Path:
    return Path(value.strip().strip('"').strip("'")).expanduser().resolve()
