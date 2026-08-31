"""Configuration for the batch recoloring tool."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Optional


@dataclass
class Settings:
    """Runtime settings. API credentials are deliberately excluded."""

    base_url: str = ""
    endpoint_path: str = "/v1/images/edits"
    model: str = "gpt-image-2"
    subject: str = "户外窗帘"  # 默认示例主体；任意主体均可（--subject 覆盖）
    profile: str = "B"
    upload_max_dimension: int = 2048
    upload_max_bytes: int = 4 * 1024 * 1024
    upload_jpeg_quality: int = 90
    connect_timeout: float = 20.0
    read_timeout: float = 300.0
    write_timeout: float = 120.0
    pool_timeout: float = 20.0
    max_safe_retries: int = 1
    retry_delay_seconds: float = 30.0
    pause_between_tasks: float = 2.0
    context_workers: int = 1
    save_every: int = 5
    jpg_quality: int = 85

    @property
    def endpoint(self) -> str:
        if not self.base_url:
            return ""
        return f"{self.base_url.rstrip('/')}/{self.endpoint_path.lstrip('/')}"

    @property
    def profile_label(self) -> str:
        return "A参考方案" if self.profile == "A" else "B增强方案"

    def validate(self) -> None:
        self.profile = self.profile.upper()
        if self.base_url and not self.base_url.startswith(("http://", "https://")):
            raise ValueError("base_url 必须以 http:// 或 https:// 开头")
        if self.profile not in {"A", "B"}:
            raise ValueError("profile 只能是 A 或 B；B为默认生产方案，A仅用于显式复检")
        if self.upload_max_dimension < 512:
            raise ValueError("upload_max_dimension 不能小于 512")
        if self.upload_max_bytes < 256 * 1024:
            raise ValueError("upload_max_bytes 不能小于 256 KB")
        if not 60 <= self.upload_jpeg_quality <= 95:
            raise ValueError("upload_jpeg_quality 必须在 60-95 之间")
        if not 60 <= self.jpg_quality <= 95:
            raise ValueError("jpg_quality 必须在 60-95 之间")
        if self.max_safe_retries not in {0, 1}:
            raise ValueError("max_safe_retries 只能是 0 或 1，禁止配置多次自动补试")
        if self.save_every < 1:
            raise ValueError("save_every 必须 >= 1")
        if self.context_workers != 1:
            raise ValueError("当前稳定版只支持单线程，context_workers 必须为 1")


def load_settings(path: Optional[Path] = None, overrides: Optional[dict[str, Any]] = None) -> Settings:
    """Load optional JSON config, then environment and CLI overrides."""

    values: dict[str, Any] = {}
    allowed = {item.name for item in fields(Settings)}
    if path and path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"配置必须是 JSON 对象：{path}")
        unknown = set(raw) - allowed
        if unknown:
            raise ValueError(f"配置包含未知字段：{', '.join(sorted(unknown))}")
        values.update(raw)

    env_map = {
        "base_url": "SUB2API_BASE_URL",
        "model": "RECOLOR_MODEL",
        "upload_max_dimension": "RECOLOR_UPLOAD_MAX_DIMENSION",
        "upload_max_bytes": "RECOLOR_UPLOAD_MAX_BYTES",
    }
    for name, env_name in env_map.items():
        raw_value = os.environ.get(env_name)
        if raw_value:
            values[name] = int(raw_value) if name in {"upload_max_dimension", "upload_max_bytes"} else raw_value

    if overrides:
        values.update({key: value for key, value in overrides.items() if value is not None})
    settings = Settings(**values)
    settings.validate()
    return settings


def public_settings(settings: Settings) -> dict[str, Any]:
    """Serializable non-secret settings for manifests and diagnostics."""

    return {**asdict(settings), "endpoint": settings.endpoint, "profile_label": settings.profile_label}
