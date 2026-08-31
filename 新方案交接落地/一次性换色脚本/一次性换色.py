#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性换色脚本：一张原图 + 一个颜色 = 一次付费图片编辑请求。

与 `正式工具_batch_recolor_tool` 保持同一技术路线，只是把批量流程收敛成单次：
  - 系统 curl 作为某次部署中经验证的传输兼容适配器；
  - 色卡中心 200×200 取色；也支持直接用 --hex 指定颜色；
  - 默认 B 增强方案；仅在显式 --profile A 时使用 A 参考方案；
  - 上传副本 EXIF 归一化、最长边压到 2048、JPEG；
  - PNG 保留模型原始字节；JPG 从 PNG 派生（quality 85、progressive）；
  - uncertain（含503）绝不自动重试；仅429或连接未建立允许一次安全补试；
  - API Key 来自环境变量，不进入 Git、日志、输出、聊天或 curl argv；仅经短期私有临时请求头文件传递，并尽力删除。

这是给“用户完全不懂 Python、由 Agent 代劳”的落地脚本。
"""

from __future__ import annotations

import argparse
import base64
import html
import binascii
import colorsys
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageOps, ImageStat, UnidentifiedImageError

# ---------------------------------------------------------------------------
# 默认值：与正式工具一致，可被环境变量或命令行覆盖。
# ---------------------------------------------------------------------------
DEFAULT_BASE_URL = ""
DEFAULT_ENDPOINT_PATH = "/v1/images/edits"
DEFAULT_MODEL = "gpt-image-2"
DEFAULT_SUBJECT = "户外窗帘"  # 默认示例主体；任意主体均可（--subject 覆盖）
DEFAULT_MAX_DIMENSION = 2048
DEFAULT_CONNECT_TIMEOUT = 20
DEFAULT_READ_TIMEOUT = 300
DEFAULT_JPG_QUALITY = 85
SAFE_RETRY_DELAY = 30
PROMPT_VERSION = "outdoor-curtain-once-v2-20260903"


def _reconfigure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError, ValueError):
            pass


class RecolorError(RuntimeError):
    pass


class SafeRetryError(RecolorError):
    """连接尚未建立，或网关明确返回429：允许有限安全补试。"""


class UncertainError(RecolorError):
    """请求可能已进入上游，禁止自动重试。"""


class FatalError(RecolorError):
    """明确被拒绝或本地不可恢复错误。"""


# ---------------------------------------------------------------------------
# 取色与提示词（与正式工具保持一致）
# ---------------------------------------------------------------------------
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


def color_from_hex(value: str) -> dict[str, Any]:
    cleaned = value.strip().lstrip("#")
    if len(cleaned) != 6:
        raise FatalError(f"--hex 格式不正确，应为 #RRGGBB，例如 #2F6B63：{value}")
    try:
        rgb = tuple(int(cleaned[index : index + 2], 16) for index in (0, 2, 4))
    except ValueError as exc:
        raise FatalError(f"--hex 不是合法十六进制颜色：{value}") from exc
    return {
        "rgb": list(rgb),
        "hex": "#" + cleaned.upper(),
        "description": color_description(rgb),
        "sample": "cli_hex",
    }


def extract_color_from_card(card_path: Path) -> dict[str, Any]:
    try:
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
    except (OSError, UnidentifiedImageError) as exc:
        raise FatalError(f"无法读取色卡图片：{card_path}") from exc
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
        raise FatalError("profile 只能是 A 或 B；B为默认生产方案，A仅用于显式复检")
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


# ---------------------------------------------------------------------------
# 上传副本准备（EXIF 归一化 + 最长边压缩 + JPEG）
# ---------------------------------------------------------------------------
def prepare_upload(source: Path, cache_dir: Path, max_dimension: int) -> Path:
    try:
        with Image.open(source) as raw:
            normalized = ImageOps.exif_transpose(raw)
            if normalized.mode in {"RGBA", "LA"} or (
                normalized.mode == "P" and "transparency" in normalized.info
            ):
                rgba = normalized.convert("RGBA")
                rgb = Image.new("RGB", rgba.size, "white")
                rgb.paste(rgba, mask=rgba.getchannel("A"))
            else:
                rgb = normalized.convert("RGB")
            rgb.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    except (OSError, UnidentifiedImageError) as exc:
        raise FatalError(f"无法解码原图：{source}") from exc

    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
    target = cache_dir / f"上传_{Path(source).stem}__{digest}.jpg"
    buffer = io.BytesIO()
    rgb.save(
        buffer,
        "JPEG",
        quality=90,
        optimize=True,
        progressive=True,
        subsampling="4:2:0",
    )
    _atomic_write_bytes(target, buffer.getvalue())
    return target


# ---------------------------------------------------------------------------
# 文件安全写入
# ---------------------------------------------------------------------------
def _atomic_write_bytes(path: Path, data: bytes) -> None:
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


def _atomic_write_text(path: Path, text: str) -> None:
    _atomic_write_bytes(path, text.encode("utf-8"))


def safe_name(text: str) -> str:
    invalid = '<>:"/\\|?*\0'
    cleaned = "".join("_" if char in invalid else char for char in text).strip().rstrip(".")
    return cleaned or "unnamed"


def _write_attempt(path: Path, payload: dict[str, Any]) -> None:
    payload["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# curl 传输（与正式工具 image_edit_client 一致）
# ---------------------------------------------------------------------------
def _parse_status(stdout: bytes) -> int:
    text = stdout.decode("ascii", "replace").strip()
    if len(text) >= 3 and text[-3:].isdigit():
        return int(text[-3:])
    return 0


def _preview(raw: bytes, limit: int = 500) -> str:
    return raw[:limit].decode("utf-8", "replace").replace("\r", " ").replace("\n", " ")


def run_curl_once(
    endpoint: str,
    api_key: str,
    model: str,
    upload_path: Path,
    prompt: str,
    request_id: str,
    connect_timeout: int,
    read_timeout: int,
) -> tuple[int, bytes, str]:
    curl = shutil.which("curl")
    if not curl:
        raise FatalError("系统未找到 curl。请先安装 curl（Windows 10+ 一般自带）。")

    response_file: Optional[Path] = None
    header_file: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(prefix="once_response_", suffix=".json", delete=False) as temp:
            response_file = Path(temp.name)
        with tempfile.NamedTemporaryFile(
            prefix="once_headers_", suffix=".txt", mode="w", encoding="utf-8", delete=False
        ) as temp:
            temp.write(f"Authorization: Bearer {api_key}\n")
            temp.write(f"x-client-request-id: {request_id}\n")
            temp.write("Expect:\n")
            header_file = Path(temp.name)
        try:
            header_file.chmod(0o600)
        except OSError:
            pass
        # 不使用 shell；凭据由权限受限的临时文件交给 curl，不出现在进程 argv。
        command = [
            curl,
            "--silent", "--show-error", "--location",
            "--connect-timeout", str(connect_timeout),
            "--max-time", str(read_timeout),
            "--output", str(response_file),
            "--write-out", "%{http_code}",
            "--request", "POST", endpoint,
            "--header", f"@{header_file}",
            "--form-string", f"model={model}",
            "--form-string", f"prompt={prompt}",
            "--form", f"image=@{upload_path};type=image/jpeg",
            "--form-string", "response_format=b64_json",
        ]
        try:
            done = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=read_timeout + connect_timeout + 15,
            )
        except subprocess.TimeoutExpired as exc:
            raise UncertainError("curl 进程超时；请求可能已进入上游，禁止自动重试") from exc
        except OSError as exc:
            raise FatalError(
                f"curl 无法启动，未提交请求：{type(exc).__name__}: {exc}"
            ) from exc

        raw = response_file.read_bytes() if response_file.exists() else b""
        status = _parse_status(done.stdout)
        stderr = done.stderr.decode("utf-8", "replace")[:500].replace("\r", " ").replace("\n", " ")
        if done.returncode != 0:
            if done.returncode in {5, 6, 7} and status == 0:
                raise SafeRetryError(f"curl 连接尚未建立（exit {done.returncode}）：{stderr or '<empty>'}")
            raise UncertainError(
                f"curl 传输异常（exit {done.returncode}, HTTP {status or 'unknown'}）：{stderr or '<empty>'}"
            )
        return status, raw, stderr
    finally:
        for temporary in (response_file, header_file):
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass


# ---------------------------------------------------------------------------
# 输出保存
# ---------------------------------------------------------------------------
def save_outputs(raw_png: bytes, png_path: Path, jpg_path: Path, jpg_quality: int) -> tuple[int, int]:
    try:
        with Image.open(io.BytesIO(raw_png)) as image:
            image.load()
            if (image.format or "").upper() != "PNG":
                raise ValueError(f"模型返回的不是 PNG，而是 {image.format}")
            size = image.size
            rgb = image.convert("RGB")
    except (OSError, UnidentifiedImageError) as exc:
        raise FatalError("模型返回内容不是可解码 PNG 图片") from exc

    _atomic_write_bytes(png_path, raw_png)
    jpg_buffer = io.BytesIO()
    rgb.save(
        jpg_buffer,
        "JPEG",
        quality=jpg_quality,
        optimize=True,
        progressive=True,
        subsampling="4:2:0",
    )
    _atomic_write_bytes(jpg_path, jpg_buffer.getvalue())
    return size


def write_review_html(
    html_path: Path,
    source: Path,
    card_or_hex: str,
    result_jpg: Path,
    color_hex: str,
    subject: str,
    status: str,
    request_id: str,
    profile_label: str = "B增强方案",
) -> None:
    def relative_url(path: Path) -> str:
        return Path(os.path.relpath(path, html_path.parent)).as_posix()

    color_safe = html.escape(color_hex, quote=True)
    card = (
        f'<figure><div class="swatch" style="background:{color_safe}"></div>'
        f'<figcaption>目标色 {html.escape(color_hex)}</figcaption></figure>'
        if card_or_hex.startswith("#")
        else (
            f'<figure><img src="{html.escape(relative_url(Path(card_or_hex).resolve()), quote=True)}" '
            'alt="色卡"><figcaption>色卡</figcaption></figure>'
        )
    )
    result = (
        f'<img src="{html.escape(relative_url(result_jpg), quote=True)}" alt="结果">'
        if result_jpg.is_file()
        else '<div class="empty">尚无结果</div>'
    )
    document = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>一次性换色审阅</title>
<style>
body{{font-family:Segoe UI,Microsoft YaHei,sans-serif;margin:24px;background:#f3f4f6;color:#172033}}
.card{{max-width:1200px;margin:0 auto;background:white;border-radius:12px;padding:18px;box-shadow:0 2px 12px #0001}}
.images{{display:grid;grid-template-columns:1fr 200px 1fr;gap:12px;align-items:start}}figure{{margin:0}}
img,.empty,.swatch{{width:100%;max-height:560px;object-fit:contain;background:#eee;border-radius:8px}}
.empty{{height:240px;display:grid;place-items:center;color:#777}}.swatch{{height:120px;border:1px solid #999}}
figcaption{{text-align:center;margin-top:6px}}.status{{padding:3px 8px;border-radius:999px;background:#e5e7eb}}
.succeeded{{background:#dcfce7;color:#166534}}.uncertain{{background:#fef3c7;color:#92400e}}
.rejected,.failed_safe{{background:#fee2e2;color:#991b1b}}
@media(max-width:800px){{.images{{grid-template-columns:1fr}}}}
</style></head><body>
<section class="card"><h1>{html.escape(subject)} · 一次性换色</h1>
<p>状态：<span class="status {html.escape(status)}">{html.escape(status)}</span> · Prompt方案：<strong>{html.escape(profile_label)}</strong> · request_id：<code>{html.escape(request_id)}</code> · 目标色 {html.escape(color_hex)}</p>
<div class="images">
  <figure><img src="{html.escape(relative_url(source), quote=True)}" alt="原图"><figcaption>原图</figcaption></figure>
  {card}
  <figure>{result}<figcaption>换色结果</figcaption></figure>
</div></section></body></html>"""
    _atomic_write_text(html_path, document)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="一次性换色：一张原图 + 一个颜色 = 一次付费图片编辑请求（Agent 代劳）。"
    )
    parser.add_argument("source", nargs="?", type=Path, help="原图路径")
    parser.add_argument("--card", type=Path, help="色卡图片路径（中心 200×200 取色）")
    parser.add_argument("--hex", help="直接用十六进制颜色，例如 #2F6B63；与 --card 二选一")
    parser.add_argument("--subject", default=DEFAULT_SUBJECT, help=f"换色主体，默认：{DEFAULT_SUBJECT}")
    parser.add_argument(
        "--profile",
        choices=["A", "B", "a", "b"],
        default="B",
        help="默认B增强方案；A仅用于用户明确选择的单项复检",
    )
    parser.add_argument("--out", type=Path, default=Path("结果"), help="输出目录，默认：结果")
    parser.add_argument("--model", default=os.environ.get("RECOLOR_MODEL", DEFAULT_MODEL))
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SUB2API_BASE_URL", DEFAULT_BASE_URL),
        help="网关 Base URL，默认读环境变量 SUB2API_BASE_URL",
    )
    parser.add_argument("--endpoint-path", default=DEFAULT_ENDPOINT_PATH)
    parser.add_argument("--max-dimension", type=int, default=DEFAULT_MAX_DIMENSION)
    parser.add_argument("--connect-timeout", type=int, default=DEFAULT_CONNECT_TIMEOUT)
    parser.add_argument("--read-timeout", type=int, default=DEFAULT_READ_TIMEOUT)
    parser.add_argument("--yes", action="store_true", help="跳过付费确认（Agent 代劳时使用）")
    parser.add_argument("--check", action="store_true", help="只做离线环境自检，不调用 API")
    parser.add_argument("--dry-run", action="store_true", help="只预览取色、提示词与请求计划，不调用 API")
    return parser.parse_args()


def endpoint_of(args: argparse.Namespace) -> str:
    if not args.base_url:
        return ""
    return f"{args.base_url.rstrip('/')}/{args.endpoint_path.lstrip('/')}"


def run_environment_check(args: argparse.Namespace) -> int:
    checks = []
    curl = shutil.which("curl")
    checks.append(("Python", True, sys.version.split()[0]))
    checks.append(("系统 curl", bool(curl), (curl or "未找到")))
    try:
        from PIL import Image  # noqa: F401

        checks.append(("Pillow", True, Image.__version__))
    except Exception as exc:
        checks.append(("Pillow", False, str(exc)))
    api_key = os.environ.get("SUB2API_API_KEY") or os.environ.get("SUB2API_KEY") or ""
    checks.append(("API Key 环境变量", bool(api_key), "已配置" if api_key else "未配置（付费请求无法执行）"))
    checks.append(("Base URL", bool(args.base_url), args.base_url or "未配置"))
    checks.append(("模型", True, args.model))

    print("\n========== 环境自检（不调用 API） ==========")
    for name, ok, detail in checks:
        print(("[通过]" if ok else "[失败]"), name, "-", detail)
    print("===========================================\n")
    if not all(item[1] for item in checks):
        print("环境尚未准备好。请把完整输出发给 Agent，不要自行反复尝试。")
        return 1
    print("环境就绪。下一步让 Agent 用 --dry-run 预览，仍不收费。")
    return 0


def main() -> int:
    _reconfigure_stdio()
    args = parse_args()

    if args.check:
        return run_environment_check(args)

    if args.source is None:
        print("ERROR: 需要提供原图路径。", file=sys.stderr)
        return 2
    source = args.source.expanduser().resolve()
    if not source.is_file():
        print(f"ERROR: 原图不存在：{source}", file=sys.stderr)
        return 2

    if args.card and args.hex:
        print("ERROR: --card 与 --hex 只能二选一。", file=sys.stderr)
        return 2
    if args.card:
        color = extract_color_from_card(args.card.expanduser().resolve())
        color_label = args.card.name
    elif args.hex:
        color = color_from_hex(args.hex)
        color_label = color["hex"]
    else:
        print("ERROR: 请用 --card 提供色卡，或用 --hex 提供颜色。", file=sys.stderr)
        return 2

    subject = args.subject.strip()
    if not subject:
        print("ERROR: --subject 不能为空。", file=sys.stderr)
        return 2
    profile = args.profile.upper()
    profile_label = "A参考方案" if profile == "A" else "B增强方案"

    prompt = build_prompt(subject, color, profile)
    endpoint = endpoint_of(args)
    if not endpoint:
        print("ERROR: 请设置 SUB2API_BASE_URL 或传入 --base-url。", file=sys.stderr)
        return 2
    out = args.out.expanduser().resolve()
    cache_dir = out / ".上传缓存"
    stem = safe_name(source.stem or "原图")
    hex_suffix = color["hex"].lstrip("#")
    base = f"{stem}__{hex_suffix}__{profile}"
    png_path = out / f"{base}_结果.png"
    jpg_path = out / f"{base}_结果.jpg"
    json_path = out / f"{base}_结果.json"
    html_path = out / f"{base}_审阅.html"
    attempt_path = out / f"{base}_attempt.json"
    identity_artifacts = (png_path, jpg_path, json_path, html_path, attempt_path)

    print("\n========== 一次性换色计划 ==========")
    print(f"原图     : {source.name}")
    print(f"颜色来源 : {color_label}")
    print(f"目标色   : {color['hex']} RGB{tuple(color['rgb'])}（{color['description']}）")
    print(f"换色主体 : {subject}")
    print(f"Prompt方案: {profile_label}")
    print(f"模型     : {args.model}")
    print(f"端点     : {endpoint}")
    print(f"新增付费调用 : 1（仅一张原图）")
    print(f"输出目录 : {out}")
    print("提示词预览：")
    print(f"  {prompt[:240]}{'...' if len(prompt) > 240 else ''}")
    print("====================================\n")

    if args.dry_run:
        print("DRY RUN 完成，没有调用 API、没有产生费用。")
        return 0

    existing_artifacts = [path for path in identity_artifacts if path.exists()]
    if existing_artifacts:
        print(
            f"ERROR: 已存在同一输出身份（原图名+颜色+方案：{base}）的目标文件或尝试记录，"
            "为避免重复付费调用和覆盖，已拒绝本次运行且不会调用 curl。",
            file=sys.stderr,
        )
        print("请 Agent 先检查以下现有文件：", file=sys.stderr)
        for path in existing_artifacts:
            print(f"  {path}", file=sys.stderr)
        print(
            "用户审阅并明确授权重新运行后，必须改用一个全新的 --out 目录；不要删除或覆盖现有文件。",
            file=sys.stderr,
        )
        return 4

    out.mkdir(parents=True, exist_ok=True)

    api_key = os.environ.get("SUB2API_API_KEY") or os.environ.get("SUB2API_KEY") or ""
    if not api_key:
        print("ERROR: 缺少 API Key。请设置环境变量 SUB2API_API_KEY。", file=sys.stderr)
        return 2

    if not args.yes:
        print("提醒：当前网关可能为明文 HTTP；图片编辑接口没有幂等键。")
        answer = input("确认开始 1 次付费图片调用？输入 YES 继续：").strip()
        if answer != "YES":
            print("已取消，没有调用 API。")
            return 0

    upload = prepare_upload(source, cache_dir, args.max_dimension)
    request_ids: list[str] = []

    attempts = 2  # 第一次 + 仅一次安全补试（只针对429或连接未建立）
    for attempt in range(1, attempts + 1):
        request_id = str(uuid.uuid4())
        request_ids.append(request_id)
        attempt_record = {
            "status": "submitted",
            "request_id": request_id,
            "request_ids": request_ids,
            "attempt": attempt,
            "source": str(source),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "subject": subject,
            "profile": profile,
            "profile_label": profile_label,
            "color": color,
            "model": args.model,
            "prompt_version": PROMPT_VERSION,
        }
        _write_attempt(attempt_path, attempt_record)
        print(f"\n开始提交，attempt={attempt}，request_id={request_id}")
        started = time.monotonic()
        try:
            status, raw, stderr = run_curl_once(
                endpoint,
                api_key,
                args.model,
                upload,
                prompt,
                request_id,
                args.connect_timeout,
                args.read_timeout,
            )
        except SafeRetryError as exc:
            attempt_record.update(status="retry_wait", error=str(exc))
            _write_attempt(attempt_path, attempt_record)
            if attempt >= attempts:
                attempt_record.update(status="failed_safe")
                _write_attempt(attempt_path, attempt_record)
                print(f"[failed_safe] 安全补试用完，停止：{exc}", file=sys.stderr)
                return 1
            print(f"[安全补试] {exc}；{SAFE_RETRY_DELAY} 秒后重连一次。")
            time.sleep(SAFE_RETRY_DELAY)
            continue
        except UncertainError as exc:
            attempt_record.update(status="uncertain", error=str(exc))
            _write_attempt(attempt_path, attempt_record)
            print(f"[uncertain] {exc}", file=sys.stderr)
            print("为避免重复扣费，已停止且不会自动重试。请按 request_id 对账。")
            return 3
        except FatalError as exc:
            attempt_record.update(status="rejected", error=str(exc))
            _write_attempt(attempt_path, attempt_record)
            print(f"[rejected] {exc}", file=sys.stderr)
            return 3

        # 下面是拿到 curl 退出后的状态分派（与正式工具一致）。
        try:
            if status == 429:
                raise SafeRetryError(f"HTTP {status}: {_preview(raw) or '<empty body>'}")
            if status == 503:
                raise UncertainError(
                    f"HTTP 503 无法证明请求未进入上游，停止并对账：{_preview(raw) or '<empty body>'}"
                )
            if status in {400, 401, 403, 404, 413, 422}:
                raise FatalError(f"HTTP {status}: {_preview(raw)}")
            if status >= 500 or status in {408, 409}:
                raise UncertainError(f"HTTP {status} 可能已进入上游：{_preview(raw)}")
            if status >= 400 or status == 0:
                raise FatalError(f"HTTP {status or 'unknown'}: {_preview(raw)}")
            try:
                payload = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise UncertainError("HTTP 2xx 但响应不是 JSON，任务可能已计费") from exc
            items = payload.get("data") or []
            item = items[0] if items and isinstance(items[0], dict) else {}
            encoded = item.get("b64_json")
            if not encoded:
                raise UncertainError("HTTP 2xx 但缺少 data[0].b64_json，任务可能已计费")
            try:
                image_bytes = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise UncertainError("返回的 b64_json 无法解码，任务可能已计费") from exc
        except SafeRetryError as exc:
            attempt_record.update(status="retry_wait", error=str(exc))
            _write_attempt(attempt_path, attempt_record)
            if attempt >= attempts:
                attempt_record.update(status="failed_safe")
                _write_attempt(attempt_path, attempt_record)
                print(f"[failed_safe] 安全补试用完，停止：{exc}", file=sys.stderr)
                return 1
            print(f"[安全补试] {exc}；{SAFE_RETRY_DELAY} 秒后重连一次。")
            time.sleep(SAFE_RETRY_DELAY)
            continue
        except UncertainError as exc:
            attempt_record.update(status="uncertain", error=str(exc))
            _write_attempt(attempt_path, attempt_record)
            print(f"[uncertain] {exc}", file=sys.stderr)
            print("为避免重复扣费，已停止且不会自动重试。请按 request_id 对账。")
            return 3
        except FatalError as exc:
            attempt_record.update(status="rejected", error=str(exc))
            _write_attempt(attempt_path, attempt_record)
            print(f"[rejected] {exc}", file=sys.stderr)
            return 3

        elapsed = round(time.monotonic() - started, 2)
        try:
            size = save_outputs(image_bytes, png_path, jpg_path, DEFAULT_JPG_QUALITY)
        except FatalError as exc:
            attempt_record.update(status="failed_safe", error=f"本地保存失败：{exc}")
            _write_attempt(attempt_path, attempt_record)
            print(f"[failed_safe] 本地保存失败：{exc}", file=sys.stderr)
            return 1

        metadata = {key: value for key, value in payload.items() if key != "data"}
        metadata.update(revised_prompt=item.get("revised_prompt"), transport="system-curl")
        result = {
            "status": "succeeded",
            "request_id": request_id,
            "request_ids": request_ids,
            "attempt": attempt,
            "model_requested": args.model,
            "model_reported": metadata.get("model"),
            "source": str(source),
            "subject": subject,
            "profile": profile,
            "profile_label": profile_label,
            "color": color,
            "prompt_version": PROMPT_VERSION,
            "prompt": prompt,
            "elapsed_seconds": elapsed,
            "output_size": list(size),
            "png": str(png_path),
            "jpg": str(jpg_path),
            "response": metadata,
        }
        _atomic_write_text(json_path, json.dumps(result, ensure_ascii=False, indent=2))
        attempt_record.update(
            status="succeeded",
            elapsed_seconds=elapsed,
            png=str(png_path),
            jpg=str(jpg_path),
        )
        _write_attempt(attempt_path, attempt_record)
        write_review_html(
            html_path,
            source,
            color_label,
            jpg_path,
            color["hex"],
            subject,
            "succeeded",
            request_id,
            profile_label,
        )

        print(f"\n成功，耗时 {elapsed}s，输出尺寸 {size}")
        print(f"PNG 母版 : {png_path}")
        print(f"JPG 预览 : {jpg_path}")
        print(f"结果记录 : {json_path}")
        print(f"审阅页   : {html_path}")
        usage = metadata.get("usage")
        if usage:
            print(f"用量     : {usage}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
