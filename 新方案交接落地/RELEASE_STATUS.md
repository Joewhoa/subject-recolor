# Release Status

Status: published to origin/main — history redacted, subject-recolor positioning applied, repo metadata set, CI verified

Date: 2026-09-02

## Project position and evolution

- The project is positioned as subject recolor for arbitrary subjects (curtain, sofa, umbrella, etc.); outdoor curtain is only the default example subject of the field-delivery layer, not the project identity.
- The repository root is the earlier reproducible engineering baseline.
- `新方案交接落地/` is the later production-delivery evolution, created because a nontechnical user had difficulty operating the CLI directly.
- The evolution adds Agent operation, beginner-facing documentation, a one-shot single-image/single-color entry point, resumable batch processing, a paid-call safety state machine, strict cache validation and human review.

## Production behavior confirmed

- Profile B is the default.
- Profile A runs only as an explicit per-item recheck; A is never added automatically and A+B is never run automatically.
- HTTP 503 is classified as uncertain and is never retried automatically.
- Only HTTP 429 and a confirmed connection-not-established failure may receive one bounded retry; `max_safe_retries` accepts only `0` or `1`.
- A local curl launch failure is fatal and is not retried.
- A request ID is trace-only metadata, not an idempotency mechanism.
- One-shot refuses a same-identity rerun when output artifacts or an attempt sidecar already exist. After human review, the user must select a fresh `--out` path.
- Across batch runs, an explicitly authorized retry of an uncertain item preserves monotonic attempt numbers and request IDs.
- The API key is injected through the environment and must not appear in Git, logs, output, chat or curl argv. Curl receives it through a short-lived private temporary header file, deleted on a best-effort basis.
- Batch cache reuse is strict: task identity and required artifact hashes must match.
- Human review remains part of production acceptance.

## Verification

Verified on 2026-09-02 with Python 3.14.7 and curl 8.21.0:

- Root baseline: 34 pytest tests passed with 83% coverage.
- Root baseline: Ruff passed.
- Field batch delivery: 13 tests passed, including a localhost fake API exercised through real system curl.
- Field one-shot delivery: 3 tests passed.
- Environment check passed.
- The local `dist/` wheel was rebuilt at SHA-256 `BC8166DD35050DB76E826598566D9AC6B87DF8B2D8A99232A26A9A0462D3B2D9` (27,975 bytes), but the README opening was tightened again afterward for the subject-recolor positioning. Rebuild before attaching a release wheel; `dist/` remains git-ignored.
- Field `SHA256SUMS.txt` contains 48 entries and every entry matches.
- Field `文件清单.txt` lists exactly the same 48 release entries.
- Field `__pycache__` directories and `.pyc` files were removed.

## Security and release hygiene

- The current candidate-file scan found no RFC1918 endpoint, real request ID, literal Bearer credential, or internal billing/usage detail.
- Ignored caches, generated outputs and local configuration remain outside the release candidate.
- No request IDs or secrets are reproduced in this document.

## Publication status and remaining checks

- History was redacted: the sole commit was rewritten via `git commit --amend` and force-pushed with `--force-with-lease` to `origin/main`. Reachable history no longer contains the two real request IDs or the internal ledger narrative. (The local reflog may still reference the old commit until GC; GitHub's unreachable objects age out separately.)
- GitHub Actions verified remotely: the latest commit `25218d0` CI run is `success` (Python 3.11/3.12/3.13 matrix).
- Repository metadata set: About description is the subject-recolor one-liner; topics are `image-editing`, `python`, `generative-ai`, `batch-processing`, `computer-vision`, `dsh`.
- `dist/` is git-ignored, so the wheel is not versioned; rebuild before attaching a release wheel (README was tightened again after the last rebuild).
- GitHub Release/tag has not been created; release remains an owner decision.
- Performed: `git push --force-with-lease origin main` (`7998938..1a03648`, then `1a03648..25218d0`). No repository creation or Release creation was performed.
