# Changelog

## Unreleased — production-delivery evolution

- Clarified that the repository root is the earlier reproducible engineering baseline and `新方案交接落地` is the later production-delivery version of the same project, not a competing duplicate.
- Recorded the direct product cause for the evolution: a genuinely non-technical user could not operate the CLI independently.
- Added an Agent-operated workflow, beginner manual and one-shot single-image/single-color entry.
- Added resumable batch operation, a paid-call safety state machine, strict cache reuse and human review.
- Defined production scheme B as the default; scheme A requires explicit per-item review, and A+B is never automatic.
- Defined HTTP 503 as uncertain with no automatic retry. Only HTTP 429 and confirmed no-connection conditions allow one bounded retry.
- Clarified that request IDs support tracing and do not provide idempotency.

## 0.1.0 — earlier reproducible engineering baseline

- Initial public-project structure.
- Generic runtime-selected subject recoloring.
- Single enhanced production prompt.
- Content-addressed task planning and safe paid-run guard.
- OpenAI-compatible image-edit gateway.
- Uncertain-timeout halt semantics.
- Exact PNG preservation, JPEG derivation and static review page.
- Offline synthetic tests and GitHub Actions CI configuration.
- `init`, `doctor`, interactive confirmation and call-count reconciliation.
- Strict task sidecars and artifact-hash cache validation.
- Input filtering, duplicate-stem protection and WebP multipart MIME support.
- Original/color-card/result triptych review page and deterministic offline demo.
- Repository-distributed DSH Skill for agent-driven batch operation.
