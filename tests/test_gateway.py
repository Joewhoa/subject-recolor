from __future__ import annotations

import base64

import httpx
import pytest

from subject_recolor.gateway import GatewayError, GatewayUncertain, OpenAICompatibleGateway


def test_gateway_sends_multipart(job_dir, png_bytes) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/images/edits"
        assert request.headers["x-client-request-id"] == "request-1"
        assert "multipart/form-data" in request.headers["content-type"]
        body = request.read()
        assert b'gpt-image-2' in body
        assert b'response_format' in body
        return httpx.Response(
            200,
            json={"data": [{"b64_json": base64.b64encode(png_bytes).decode()}], "model": "test"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    gateway = OpenAICompatibleGateway("https://example.test/v1", "secret", client=client)
    result = gateway.edit(job_dir / "input" / "scene.png", "prompt", "gpt-image-2", "request-1")
    assert result.png == png_bytes
    assert result.response["model"] == "test"


def test_gateway_uses_webp_mime(job_dir, png_bytes) -> None:
    from PIL import Image

    source = job_dir / "input" / "web.webp"
    Image.new("RGB", (64, 64), "white").save(source, "WEBP")

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        assert b"Content-Type: image/webp" in body
        return httpx.Response(
            200,
            json={"data": [{"b64_json": base64.b64encode(png_bytes).decode()}]},
        )

    gateway = OpenAICompatibleGateway(
        "https://example.test/v1",
        "secret",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    gateway.edit(source, "prompt", "gpt-image-2", "request-2")


@pytest.mark.parametrize("status", [400, 401, 403, 429, 503])
def test_gateway_preserves_explicit_http_status(job_dir, status) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=f"gateway-status-{status}")

    gateway = OpenAICompatibleGateway(
        "https://example.test/v1",
        "secret",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(GatewayError) as caught:
        gateway.edit(job_dir / "input" / "scene.png", "prompt", "gpt-image-2", "request")
    assert caught.value.status_code == status


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"data": []},
        {"data": [{}]},
        {"data": [{"b64_json": "not valid base64!"}]},
    ],
)
def test_gateway_rejects_invalid_success_schema(job_dir, payload) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    gateway = OpenAICompatibleGateway(
        "https://example.test/v1",
        "secret",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(GatewayError, match="invalid gateway response"):
        gateway.edit(job_dir / "input" / "scene.png", "prompt", "gpt-image-2", "request")


def test_gateway_transport_failure_is_uncertain(job_dir) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("provider timed out", request=request)

    gateway = OpenAICompatibleGateway(
        "https://example.test/v1",
        "secret",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(GatewayUncertain, match="transport outcome is unknown"):
        gateway.edit(job_dir / "input" / "scene.png", "prompt", "gpt-image-2", "request")
