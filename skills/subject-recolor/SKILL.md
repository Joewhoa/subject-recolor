---
name: subject-recolor
description: "Operate the Subject Recolor CLI for safe batch image editing from source photos and color cards. Use when the user asks for 批量换色、主体换色、按色卡生图、把窗帘/沙发/雨伞等指定主体改色, or asks an agent to plan, execute, resume, diagnose, or review a subject-recolor job. Enforces a paid-call preflight and never retries uncertain image edits automatically."
---

# Subject Recolor Agent Workflow

Use the repository CLI to batch-edit a user-selected subject from color-card images. The subject is runtime data; never assume it is a curtain.

## What this Skill is

A Skill is an instruction playbook for the agent. It tells the agent how to use the project safely and consistently. It is not an image model, API gateway, or runtime plugin. This project does not require a dynamic Cordis plugin.

## Preconditions

- Work from the `subject-recolor` repository or pass its workspace explicitly.
- A job directory contains `job.toml`, `input/`, and `color_cards/`.
- Paid runs require `IMAGE_API_BASE_URL` and `IMAGE_API_KEY` in the process environment.
- Never print, read back, persist, or commit the API key.

## Non-idempotent Paid Request Model

The image edit endpoint has no verified idempotency guarantee.

| Status | Meaning | Required action |
|---|---|---|
| `submitted` | Local request started | Preserve request ID |
| `succeeded` | Response and artifacts confirmed | May resume/cache |
| `failed_safe` | Explicit non-success HTTP response | Report; do not hide |
| `rejected` | 400/401/403 | Stop the batch and fix configuration |
| `uncertain` | Timeout/transport interruption; upstream outcome unknown | Stop and NEVER auto-retry |

## Standard Workflow

1. Clarify only missing business data: workspace/job date and selected subject. Do not invent a subject or color-card scope.
2. Run environment diagnostics without making an image request:
   ```bash
   subject-recolor doctor --workspace <workspace>
   ```
3. Always run a machine-readable plan first:
   ```bash
   subject-recolor plan --workspace <workspace> --date <date> --json
   ```
   Optional controlled smoke scope:
   ```bash
   subject-recolor plan --workspace <workspace> --date <date> --inputs <stem> --cards <stem> --limit 1
   ```
4. Parse and report: job, subject, model, tasks, complete, repair_jpg, and `new_calls`. State that `new_calls` are paid image-edit requests.
5. Obtain direct user confirmation unless the user already explicitly waived a second confirmation for this exact scope.
6. Execute exactly once with the preflight count pinned:
   ```bash
   subject-recolor run --workspace <workspace> --date <date> --expect-calls <new_calls> --max-paid-calls <approved_limit> --yes
   ```
   Use a shell timeout longer than the CLI's per-image timeout. For a large batch, use a managed background job and track its job ID.
7. Interpret exit codes: `0` success, `1` safe failures occurred, `2` input/configuration/approval error, `3` halted because the outcome may be uncertain or the request was rejected.
8. On `uncertain`, report the request ID from `output/run.jsonl`; do not retry or create a replacement attempt unless the user explicitly decides after reviewing potential duplicate billing.
9. Build or refresh the review page:
   ```bash
   subject-recolor review --workspace <workspace> --date <date>
   ```
10. Deliver the `output/review.html` path and summarize artifact counts and statuses. Human semantic approval remains required.

## Preflight Report Template

```text
任务：<date>
主体：<subject>
模型：<model>
原图 × 色卡：<inputs> × <cards>
计划任务：<tasks>
已完成：<complete>
仅补 JPG：<repair_jpg>
新增付费调用：<new_calls>
预计最终产物：<expected_png> PNG + <expected_jpg> JPG
```

## Human Review Checklist

- Every selected-subject instance changed color, including distant or occluded instances.
- Non-target objects and composition stayed stable.
- Material, texture, folds or structural details remained believable.
- Dark colors retain detail; light colors are not blown out.
- No edge bleeding, halos, or background contamination.

## Prohibited Actions

- Never use a text-to-image tool as a silent fallback for an image-edit job.
- Never select the subject, cards, or date on the user's behalf when ambiguous.
- Never skip `plan` before a paid run.
- Never run without reconciling `--expect-calls`.
- Never automatically retry `uncertain`.
- Never claim pixel-perfect HEX compliance or replace human semantic review.
- Never publish private source images, credentials, or full Base64 responses.

## Troubleshooting

- No job found: check `job.toml`, `input/`, `color_cards/`, and the accepted date format.
- Duplicate stem error: rename same-stem files such as `scene.jpg` and `scene.png`.
- `new_calls` unexpectedly increased: task content, subject, model, prompt, or metadata changed; do not override the strict cache.
- HTTP 401/403: stop and fix credentials or gateway permissions.
- HTTP URL warning: explain that images and credentials are transmitted without TLS.
- Exit 3 / `uncertain`: inspect `output/run.jsonl`, report the request ID, and stop.
