"""Curl-based image-edit client with conservative billing-safe error handling.

One deployment showed a client-specific compatibility difference, so its
validated system-curl route is retained as a transport adapter. Python still
owns planning, checkpoints, retry classification, parsing, and artifacts.
"""
from __future__ import annotations
import base64, binascii, json, shutil, subprocess, tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from ..config import Settings

@dataclass
class APIResult:
    image_bytes: bytes
    metadata: dict[str, Any]

class RecolorAPIError(RuntimeError):
    def __init__(self, message: str, *, http_status: Optional[int] = None, retry_after: Optional[float] = None):
        super().__init__(message); self.http_status = http_status; self.retry_after = retry_after
class SafeRetryError(RecolorAPIError): pass
class UncertainError(RecolorAPIError): pass
class FatalError(RecolorAPIError): pass

def _preview(raw: bytes, limit: int = 500) -> str:
    return raw[:limit].decode("utf-8", "replace").replace("\r", " ").replace("\n", " ")

class ImageEditClient:
    """Submit exactly one image with a fresh system-curl process/connection."""
    def __init__(self, settings: Settings, api_key: str):
        self.settings, self.api_key = settings, api_key
        self.curl = shutil.which("curl")
        if not self.curl:
            raise FatalError("系统未找到 curl。请先安装 curl，再运行环境自检。")
    def reconnect(self) -> None: return None  # every edit is already a fresh process
    def close(self) -> None: return None
    def __enter__(self) -> "ImageEditClient": return self
    def __exit__(self, *_: object) -> None: self.close()

    def edit(self, upload_path: Path, prompt: str, request_id: str) -> APIResult:
        if not isinstance(upload_path, Path) or not upload_path.is_file():
            raise FatalError(f"单图上下文缺少有效上传图片：{upload_path}")
        response_file: Optional[Path] = None
        header_file: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(prefix="recolor_response_", suffix=".json", delete=False) as temp:
                response_file = Path(temp.name)
            with tempfile.NamedTemporaryFile(
                prefix="recolor_headers_", suffix=".txt", mode="w", encoding="utf-8", delete=False
            ) as temp:
                temp.write(f"Authorization: Bearer {self.api_key}\n")
                temp.write(f"x-client-request-id: {request_id}\n")
                temp.write("Expect:\n")
                header_file = Path(temp.name)
            try:
                header_file.chmod(0o600)
            except OSError:
                pass
            # The credential stays out of process argv; curl reads the private temporary headers file.
            command = [self.curl, "--silent", "--show-error", "--location",
                "--connect-timeout", str(self.settings.connect_timeout),
                "--max-time", str(self.settings.read_timeout),
                "--output", str(response_file), "--write-out", "%{http_code}",
                "--request", "POST", self.settings.endpoint,
                "--header", f"@{header_file}",
                "--form-string", f"model={self.settings.model}",
                "--form-string", f"prompt={prompt}",
                "--form", f"image=@{upload_path};type=image/jpeg",
                "--form-string", "response_format=b64_json"]
            try:
                done = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, check=False,
                    timeout=self.settings.read_timeout + self.settings.connect_timeout + 15)
            except subprocess.TimeoutExpired as exc:
                raise UncertainError("curl进程超时；请求可能已进入上游，禁止自动重提") from exc
            except OSError as exc:
                raise FatalError(
                    f"curl无法启动，未提交请求：{type(exc).__name__}: {exc}"
                ) from exc

            raw = response_file.read_bytes() if response_file.exists() else b""
            status_text = done.stdout.decode("ascii", "replace").strip()
            status = int(status_text[-3:]) if len(status_text) >= 3 and status_text[-3:].isdigit() else 0
            stderr = done.stderr.decode("utf-8", "replace")[:500].replace("\r", " ").replace("\n", " ")
            if done.returncode != 0:
                if done.returncode in {5, 6, 7} and status == 0:
                    raise SafeRetryError(f"curl连接尚未建立（exit {done.returncode}）：{stderr or '<empty stderr>'}")
                raise UncertainError(
                    f"curl传输异常（exit {done.returncode}, HTTP {status or 'unknown'}）；请求可能已进入上游：{stderr or '<empty stderr>'}",
                    http_status=status or None)
            preview = _preview(raw)
            if status == 429:
                raise SafeRetryError(f"HTTP {status}: {preview or '<empty body>'}", http_status=status)
            if status == 503:
                raise UncertainError(
                    f"HTTP 503 无法证明请求未进入上游，停止并对账：{preview or '<empty body>'}",
                    http_status=status,
                )
            if status in {400, 401, 403, 404, 413, 422}:
                raise FatalError(f"HTTP {status}: {preview}", http_status=status)
            if status >= 500 or status in {408, 409}:
                raise UncertainError(f"HTTP {status} 可能已进入上游，禁止自动重提：{preview}", http_status=status)
            if status >= 400 or status == 0:
                raise FatalError(f"HTTP {status or 'unknown'}: {preview}", http_status=status or None)
            try:
                payload = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise UncertainError("HTTP 2xx 但响应不是JSON，任务可能已计费") from exc
            items = payload.get("data") or []
            item = items[0] if items and isinstance(items[0], dict) else {}
            encoded = item.get("b64_json")
            if not encoded:
                raise UncertainError("HTTP 2xx 但缺少 data[0].b64_json，任务可能已计费")
            try:
                image_bytes = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise UncertainError("返回的 b64_json 无法解码，任务可能已计费") from exc
            metadata = {key: value for key, value in payload.items() if key != "data"}
            metadata.update(revised_prompt=item.get("revised_prompt"), transport="system-curl")
            return APIResult(image_bytes, metadata)
        finally:
            for temporary in (response_file, header_file):
                if temporary is not None:
                    try:
                        temporary.unlink(missing_ok=True)
                    except OSError:
                        pass
