"""Input compression cache and output image conversion."""

from __future__ import annotations

import io
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from ..config import Settings
from ..utils.files import atomic_write_bytes, safe_name, sha256_file, valid_output_image


@dataclass(frozen=True)
class PreparedImage:
    original_path: str
    upload_path: str
    original_sha256: str
    original_bytes: int
    upload_bytes: int
    original_size: tuple[int, int]
    upload_size: tuple[int, int]
    mime_type: str

    def to_dict(self) -> dict:
        return asdict(self)


def _encode_jpeg(image: Image.Image, quality: int) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=quality, optimize=True, progressive=True, subsampling="4:2:0")
    return buffer.getvalue()


def prepare_upload(source: Path, cache_dir: Path, settings: Settings) -> PreparedImage:
    """Create a cached, EXIF-normalized JPEG upload copy without changing the source."""

    digest = sha256_file(source)
    cache_name = f"{safe_name(source.stem)}__{digest[:12]}_{settings.upload_max_dimension}_{settings.upload_jpeg_quality}.jpg"
    target = cache_dir / cache_name
    original_bytes = source.stat().st_size

    with Image.open(source) as raw:
        normalized = ImageOps.exif_transpose(raw)
        original_size = normalized.size
        if normalized.mode in {"RGBA", "LA"} or (normalized.mode == "P" and "transparency" in normalized.info):
            rgba = normalized.convert("RGBA")
            rgb = Image.new("RGB", rgba.size, "white")
            rgb.paste(rgba, mask=rgba.getchannel("A"))
        else:
            rgb = normalized.convert("RGB")
        rgb.thumbnail(
            (settings.upload_max_dimension, settings.upload_max_dimension),
            Image.Resampling.LANCZOS,
        )

        if not valid_output_image(target) or target.stat().st_size > settings.upload_max_bytes:
            quality = settings.upload_jpeg_quality
            encoded = _encode_jpeg(rgb, quality)
            while len(encoded) > settings.upload_max_bytes and quality > 70:
                quality -= 5
                encoded = _encode_jpeg(rgb, quality)
            while len(encoded) > settings.upload_max_bytes and max(rgb.size) > 768:
                new_size = (max(1, int(rgb.width * 0.85)), max(1, int(rgb.height * 0.85)))
                rgb = rgb.resize(new_size, Image.Resampling.LANCZOS)
                encoded = _encode_jpeg(rgb, max(70, quality))
            if len(encoded) > settings.upload_max_bytes:
                raise ValueError(
                    f"压缩后仍超过限制：{source.name} -> {len(encoded) / 1024 / 1024:.2f} MB"
                )
            atomic_write_bytes(target, encoded)

    with Image.open(target) as check:
        upload_size = check.size
    return PreparedImage(
        original_path=str(source),
        upload_path=str(target),
        original_sha256=digest,
        original_bytes=original_bytes,
        upload_bytes=target.stat().st_size,
        original_size=original_size,
        upload_size=upload_size,
        mime_type="image/jpeg",
    )


def save_model_outputs(raw_png: bytes, png_path: Path, jpg_path: Path, jpg_quality: int) -> tuple[int, int]:
    """Atomically preserve the model PNG and derive a progressive RGB JPG."""

    try:
        with Image.open(io.BytesIO(raw_png)) as image:
            image.load()
            if (image.format or "").upper() != "PNG":
                raise ValueError(f"模型返回的不是 PNG，而是 {image.format}")
            size = image.size
            rgb = image.convert("RGB")
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError("模型返回内容不是可解码图片") from exc

    atomic_write_bytes(png_path, raw_png)
    jpg_buffer = io.BytesIO()
    rgb.save(
        jpg_buffer,
        "JPEG",
        quality=jpg_quality,
        optimize=True,
        progressive=True,
        subsampling="4:2:0",
    )
    atomic_write_bytes(jpg_path, jpg_buffer.getvalue())
    return size


def repair_jpg(png_path: Path, jpg_path: Path, jpg_quality: int) -> tuple[int, int]:
    with Image.open(png_path) as image:
        image.load()
        size = image.size
        rgb = image.convert("RGB")
    buffer = io.BytesIO()
    rgb.save(buffer, "JPEG", quality=jpg_quality, optimize=True, progressive=True, subsampling="4:2:0")
    atomic_write_bytes(jpg_path, buffer.getvalue())
    return size
