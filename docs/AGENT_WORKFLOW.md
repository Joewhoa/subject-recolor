# Agent-driven Batch Workflow

Subject Recolor was designed to be operable both by a human and by a DSH conversation agent.

The division of responsibility is deliberate:

- **CLI:** hard guarantees—task discovery, call-count reconciliation, paid-run confirmation, strict cache, attempt log, uncertain halt and artifacts.
- **Skill:** agent behavior—when to plan, what to report, when to ask the user, how to interpret status and what must never be retried.
- **Image gateway:** model execution only.

This keeps safety rules enforceable even if an agent misses an instruction. The Skill improves convenience, but it is not the sole safety boundary.

## Recommended agent sequence

```text
User request
  → agent loads Skill
  → doctor
  → plan
  → agent reports new_calls
  → user confirms
  → run --expect-calls N --yes
  → review
  → human visual approval
```

`--expect-calls N` prevents a stale conversational plan from silently expanding into a larger paid batch if files change between planning and execution.
