# GitHub Maintenance Agent Handoff

## Repository identity

- Target account: `https://github.com/Joewhoa/`
- Expected repository: `subject-recolor`
- Do not publish or create a repository until the human owner explicitly asks.
- The repository root is the earlier reusable engineering baseline.
- `新方案交接落地/` is the later field-delivery version created because non-technical users could not operate the engineering CLI reliably.

## Portfolio narrative

Present the project as a production case study:

```text
reusable semantic recoloring pipeline
→ real-user operation difficulty
→ Agent-mediated beginner workflow
→ one-shot and resumable batch local tools
→ paid-call uncertainty controls and human review
```

Do not describe the two versions as competing implementations. The field-delivery layer is later productization of the earlier engineering work.

## Product behavior

- B is the default production profile.
- A is an explicit optional fallback for selected review tasks.
- Never run A+B automatically.
- One-shot tool: one source plus one card/HEX, for a quick Agent-operated trial; it accepts explicit `--profile A|B` and writes profile-distinct output names.
- Batch tool: sources × cards, preparation cache, checkpoint, event ledger and review page.
- 503 is `uncertain` and is not retried automatically.
- Only HTTP 429 and a confirmed connection-not-established condition may receive a bounded retry; `max_safe_retries` is hard-limited to `0` or `1`.
- Curl launch failure is local fatal and is not retried.
- Request IDs are trace identifiers, not idempotency keys.

## Public release decisions already applied

- Removed bundled `.venv`, Python caches and macOS metadata.
- Added field-delivery `.gitignore` and MIT `LICENSE`.
- Removed the real deployment endpoint; no private gateway is baked into code or docs, and runtime requires `SUB2API_BASE_URL` or `--base-url`.
- Redacted production request IDs, local paths, exact response sizes and billing-adjacent values.
- API keys must never enter Git, persistent configuration, application logs, terminal/chat, output artifacts or curl argv. The tool reads the key from the environment, places it only in a permission-restricted short-lived curl header file, and deletes that file best-effort after each call. A permission or cleanup failure is local security hygiene requiring Agent inspection; do not claim an impossible guarantee that no local residue can ever remain.
- Added one-shot attempt sidecars for submitted/uncertain/rejected/succeeded tracking.
- Added batch strict metadata cache with task ID and PNG/JPG SHA-256 checks.
- Added duplicate normalized-stem rejection.
- Rebuilt `文件清单.txt` and `SHA256SUMS.txt`.

## Verification before publication

Run from the repository root:

```powershell
python -m pytest
python -m ruff check .
```

Run field-delivery tests:

```powershell
cd 新方案交接落地/正式工具_batch_recolor_tool
$env:PYTHONPATH='.'
python -m unittest -v tests.test_offline tests.test_curl_local_integration

cd ../一次性换色脚本
python -m unittest -v test_once_offline
```

Verify release hygiene and checksums without executing a paid request:

```powershell
cd 新方案交接落地
python 正式工具_batch_recolor_tool/check_environment.py
# Verify every SHA256SUMS.txt entry with Get-FileHash.
# Search for private endpoints, keys, Bearer values and unredacted UUIDs.
# Inspect `git status --short --ignored` and `git add -nA` before commit.
```

Expected field-delivery result at handoff: 13 batch tests and 3 one-shot tests pass. No paid API call is required for release verification.

## GitHub maintenance tasks

1. Confirm author identity and repository URL with the human owner.
2. Review staged files, especially licensed example images and generated README assets.
3. Keep runtime output ignored.
4. Preserve MIT for code and CC BY-SA attribution for public furniture images/results.
5. Rebuild the wheel because source changed after the last recorded artifact hash.
6. Run CI locally where practical, then publish only after explicit owner authorization.
7. Do not restore private deployment endpoints or request IDs for a more detailed demo.

## Suggested README emphasis

Lead with the working recoloring CLI and real licensed result. Then explain the field-delivery evolution: users who could not operate the engineering CLI received an Agent-run one-shot path, a resumable batch path, beginner instructions, fee safety and local review artifacts.
