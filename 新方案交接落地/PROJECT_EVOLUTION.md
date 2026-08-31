# Project Evolution and Repository Positioning

## Timeline

### Phase 1: engineering baseline (`subject-recolor`)

The repository root is the earlier engineering version. It established the reusable business core:

- arbitrary runtime-selected subjects;
- color-card sampling;
- content-addressed task identity;
- strict artifact metadata;
- plan/run/review CLI;
- non-idempotent request safety;
- offline tests and a licensed public demo.

This phase proved the workflow and made it suitable for engineering review and portfolio reproduction.

### Phase 2: field delivery (`新方案交接落地`)

The later production-delivery version was created after real users had difficulty operating the engineering CLI. The requirement changed from “provide a correct tool” to “let a non-technical user complete work safely with an Agent acting as the operator.”

This phase added two local entry points:

1. **one-shot tool**: one source image plus one card/HEX color, designed for the simplest Agent-mediated request;
2. **batch tool**: multiple sources × color cards with preparation cache, checkpoint, event ledger and local review page.

It also added:

- a complete beginner guide;
- an Agent runbook;
- copy-ready natural-language requests;
- fee and uncertainty handling instructions;
- system-curl transport as a deployment compatibility adapter;
- local installation launchers.

## Public repository narrative

The two phases are not competing implementations. The root package is the earlier reusable engineering baseline; the field-delivery directory is the later productization layer built in response to user-operability problems.

The portfolio story is:

```text
working engineering pipeline
→ real-user operation difficulty
→ Agent-mediated beginner workflow
→ one-shot and batch local delivery tools
→ explicit paid-call safety and human review
```

## Current public recommendation

- Keep the root package as the reference implementation and testable library.
- Present the field-delivery tools as later case-study applications.
- Use profile B as the default production profile; profile A is an explicitly optional per-item re-check profile — never default to an A+B dual run.
- Use the one-shot tool only for a single image plus a single color; the batch tool is the default production entry for many images × many cards.
- Keep deployment hosts and gateway IPs/ports out of code and Git; inject the endpoint at runtime and use `https://your-image-gateway.example` in public examples.
- Keep API keys out of Git, persistent configuration, application logs, terminal/chat, output artifacts and curl argv. Read them from the process environment, place them only in a permission-restricted short-lived curl header file, and delete that file best-effort after each call. Treat permission or cleanup failure as local security hygiene requiring Agent inspection; do not promise that local residue is impossible.
- Treat request IDs only as trace identifiers, never as idempotency keys.
- Describe the curl change as a compatibility difference observed in one deployment, with system curl as that deployment's verification adapter — not a universal failure of `httpx`.
- Default HTTP 503 to `uncertain` (no automatic retry). Only HTTP 429 or confirmed connection-not-established may receive a bounded retry, with the retry count hard-limited to zero or one; curl launch failure is local fatal and is not retried.
