# Image Edit API Contract

Subject Recolor requires a source-image editing endpoint. A text-to-image generation endpoint is not a compatible fallback.

## Request

```text
POST {IMAGE_API_BASE_URL.rstrip('/')}/images/edits
Authorization: Bearer <IMAGE_API_KEY>
Content-Type: multipart/form-data
```

Fields:

```text
model           = <configured edit-capable model ID>
prompt          = <UTF-8 edit instruction>
response_format = b64_json
image           = <JPEG, PNG or WebP source file>
```

The baseline workflow does not send a mask.

## Response

The client expects:

```json
{
  "data": [
    {
      "b64_json": "<Base64-encoded PNG>",
      "revised_prompt": "<optional>"
    }
  ]
}
```

The decoded artifact must be a valid PNG and preserve the source aspect ratio within a tolerance of `0.01`. URL-only responses are not currently supported.

## Safety semantics

Image-edit requests are considered non-idempotent unless the gateway documents a stronger guarantee:

- timeout, disconnect or transport error → `uncertain`, halt, never retry automatically;
- HTTP 400/401/403 → `rejected`, halt;
- other explicit HTTP errors → `failed_safe`;
- malformed responses or invalid artifacts → `failed_safe`.

`x-client-request-id` is sent as a correlation identifier. It is not assumed to be an idempotency key.

## Configuration

Set credentials only in the process environment:

```text
IMAGE_API_BASE_URL
IMAGE_API_KEY
IMAGE_MODEL (optional)
```

The repository does not automatically load `.env` files and must not contain real endpoints, credentials, Authorization headers or provider-specific private deployment data.

Before a paid run:

```bash
subject-recolor doctor
subject-recolor plan --date <job> --json
subject-recolor run --date <job> --expect-calls <N> --max-paid-calls <N> --yes
```
