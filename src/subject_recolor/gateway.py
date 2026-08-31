from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Protocol

import httpx

from .models import EditResult


class GatewayError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class GatewayUncertain(GatewayError):
    """The server may have accepted the edit; retrying could duplicate cost."""


class ImageEditGateway(Protocol):
    def edit(self, source: Path, prompt: str, model: str, request_id: str) -> EditResult: ...


class OpenAICompatibleGateway:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 240,
        client: httpx.Client | None = None,
    ) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        if not api_key:
            raise ValueError("api_key cannot be empty")
        self.endpoint = base_url.rstrip("/") + "/images/edits"
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self._client = client

    def edit(self, source: Path, prompt: str, model: str, request_id: str) -> EditResult:
        client = self._client or httpx.Client(follow_redirects=True)
        owns_client = self._client is None
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }
        try:
            mime = mime_types[source.suffix.lower()]
        except KeyError as exc:
            raise ValueError(f"unsupported source format: {source.suffix}") from exc
        try:
            with source.open("rb") as stream:
                response = client.post(
                    self.endpoint,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "x-client-request-id": request_id,
                    },
                    data={
                        "model": model,
                        "prompt": prompt,
                        "response_format": "b64_json",
                    },
                    files={"image": (source.name, stream, mime)},
                    timeout=self.timeout_seconds,
                )
        except httpx.TransportError as exc:
            raise GatewayUncertain(f"transport outcome is unknown: {type(exc).__name__}") from exc
        finally:
            if owns_client:
                client.close()

        if response.status_code >= 400:
            preview = response.text[:500].replace(self.api_key, "<redacted>")
            raise GatewayError(f"HTTP {response.status_code}: {preview}", response.status_code)
        try:
            payload: dict[str, Any] = response.json()
            item = payload.get("data", [{}])[0]
            encoded = item.get("b64_json")
            if not encoded:
                raise ValueError("missing data[0].b64_json")
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            raise GatewayError(f"invalid gateway response: {exc}") from exc
        metadata = {key: value for key, value in payload.items() if key != "data"}
        metadata["revised_prompt"] = item.get("revised_prompt")
        return EditResult(png=raw, response=metadata)
