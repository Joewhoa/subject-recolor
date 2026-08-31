# GitHub Release Checklist

This checklist is for the owner or an explicitly authorized maintainer of the public GitHub repository under https://github.com/Joewhoa/.

No item below claims that GitHub settings, remote Actions runs or release state have been verified remotely.

## Existing repository state

- [x] Git repository is already initialized in this directory.
- [x] Current branch is `main`.
- [x] Remote `origin` is configured.
- [x] `[project.urls]` locally contains the exact `https://github.com/Joewhoa/subject-recolor` URLs, consistent with the configured `origin`; this does not imply remote access or verification.
- [x] Public author name set to `joewhoa` in `pyproject.toml` and `LICENSE`.
- [ ] The repository owner may add topics such as `image-editing`, `python`, `generative-ai`, `computer-vision`, `batch-processing`, `dsh`.

## Required pre-push checks

Run locally from the repository root:

```powershell
python -m pip install -e ".[dev]"
python -m ruff check .
python -m pytest --cov=subject_recolor --cov-report=term-missing

Push-Location "新方案交接落地/正式工具_batch_recolor_tool"
$env:PYTHONPATH = "."
python -m unittest -v tests.test_offline tests.test_curl_local_integration
Pop-Location

Push-Location "新方案交接落地/一次性换色脚本"
python -m unittest -v test_once_offline
Pop-Location

python -m pip wheel . --no-deps --wheel-dir dist
subject-recolor demo --workspace demo-workspace
```

Expected local field-delivery gate: 13 batch tests and 3 one-shot tests pass. Delete or isolate stale `dist/` output first, rebuild the wheel, and inspect the newly produced artifact rather than reusing an earlier wheel.

## Dry-run staging and hygiene

Before any staging or commit, preview exactly what `git add -A` would include:

```bash
git status --short --branch
git status --ignored
git add -nA
git diff --check
```

- [ ] `git add -nA` contains only intended public files and no parent-directory material.
- [ ] Caches, `.coverage`, `dist/`, runtime workspaces and generated `output/` files are ignored or deliberately excluded.
- [ ] No API keys, Authorization headers, private hosts, customer images, real request IDs, exact token usage or internal accounting narrative are tracked.
- [ ] Keep `docs/IMAGE_EDIT_API.md`; do not restore internal API operational handoff files.
- [ ] Preserve `examples/public-furniture-test/ATTRIBUTION.md` and `SOURCES.json`.
- [ ] Keep the README attribution adjacent to the original/result images.
- [ ] The original Kubus photograph and modified result remain CC BY-SA 3.0; source code remains MIT.
- [ ] Inspect the rebuilt wheel contents and metadata for unexpected files or private data.

## Reachable-history blocker

Current-candidate hygiene and reachable Git history are separate checks. The working-tree `examples/public-furniture-test/EVALUATION.md` is redacted, but the sole reachable `HEAD`/`origin/main` history still contains two real request IDs and internal ledger narrative.

- [ ] **Release blocker:** resolve the sensitive content in reachable history before public release. A normal new commit does not erase earlier objects or text from Git history. Complete removal requires an owner-approved history rewrite and remote replacement; no history rewrite, force-push or remote replacement is authorized in this maintenance pass.

Only after the dry run is clean, stage deliberately and inspect the index:

```bash
git add -A
git status --short
git diff --cached --stat
git diff --cached --check
```

Suggested commit message:

```text
feat: release safe subject recolor pipeline
```

## GitHub settings to verify by owner

These are owner-side tasks, not remotely verified facts:

- [ ] Verify Actions is enabled and confirm the configured Python matrix passes on GitHub.
- [ ] Enable secret scanning and push protection when available.
- [ ] Enable Dependabot alerts.
- [ ] Add a concise About description and website/demo link if one exists.
- [ ] Optionally protect `main` after the first successful remote CI run.

## Release

- [ ] Create tag `v0.1.0` only after the owner confirms CI passes on `main`.
- [ ] Attach the freshly rebuilt wheel only if binary release artifacts are desired.
- [ ] Use `CHANGELOG.md` as the basis for release notes.
- [ ] Do not publish to PyPI until package-name ownership and long-term versioning are intentionally decided.
- [ ] Do not push commits, branches or tags without explicit repository-owner authorization for that exact push.

## Known limitations to disclose

- The real portfolio test covers one clean, single-sofa image. The more difficult multi-sofa showroom case has not been established by the published evidence.
- The workflow uses semantic editing without a mask; pixel-perfect background invariance is not guaranteed.
- The root repository is the earlier reproducible engineering baseline. `新方案交接落地` is its later production-delivery evolution for a non-technical user, not a competing duplicate project.
