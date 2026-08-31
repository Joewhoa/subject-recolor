# Architecture

## Pipeline

```text
job discovery → color sampling → cartesian task planning → explicit approval
→ image edit gateway → atomic PNG/JPG storage → event ledger → review page
```

## Modules

- `color.py`: validated center-mean color sampling and diagnostics.
- `prompt.py`: one generic enhanced prompt for arbitrary user-selected subjects.
- `planner.py`: job discovery, Cartesian expansion and content-addressed task IDs.
- `gateway.py`: OpenAI-compatible `/images/edits` adapter and error semantics.
- `pipeline.py`: strict sidecar cache validation and no-idempotency-aware state transitions.
- `artifacts.py`: exact PNG preservation, JPEG derivation and validation.
- `config.py`: `job.toml` initialization and loading.
- `demo.py`: deterministic, synthetic-only full-pipeline demo.
- `doctor.py`: zero-image-call environment diagnostics.
- `review.py`: original/card/result triptych review gallery.
- `cli.py`: safe init/plan/run/review/doctor/demo interface.

## Design decisions

### One prompt profile

The project retains only the enhanced production prompt. Subject names are runtime input, so the same pipeline can target curtains, sofas, umbrellas and other objects without product-specific branches.

### No silent text-to-image fallback

A recolor job requires an input image. If an adapter cannot perform image editing, it must fail rather than silently call a text-to-image endpoint and redraw the scene.

### Uncertain transport outcome

A timeout occurs after a request may already have reached the provider. Because the image endpoint has no verified idempotency contract, retrying could duplicate cost. The pipeline records `uncertain` and halts.

### Content identity

`task_id` covers source bytes, color-card bytes, subject, model, prompt version and rendered prompt. A changed subject or prompt creates a new task identity even when filenames are unchanged. A result is reusable only when its sidecar task ID and both artifact hashes match; filenames alone never establish cache identity.

### Agent safety

The CLI owns hard guarantees. A DSH Skill guides the conversational workflow but cannot weaken `--expect-calls`, strict cache checks or the uncertain-result halt. This separation makes the repository useful both interactively and through an agent.

### Human-in-the-loop quality

Automated checks verify structure and artifacts, not semantic correctness. The review page makes human approval an explicit part of the workflow.
