# Portfolio Notes

## One-line description

Built an earlier reproducible engineering baseline for subject recoloring, then evolved it into a production-delivery workflow after a genuinely non-technical user could not operate the CLI independently.

## Evolution, not duplication

The repository root is the earlier reproducible engineering baseline: deterministic N×M planning, guarded paid calls, artifact production, strict cache validation and human review. `新方案交接落地` is the later production-delivery version of the same project, not a competing duplicate project.

That later version was caused directly by observed usability failure: a genuinely non-technical user could not independently operate the CLI. The production-delivery evolution therefore adds:

- an Agent-operated workflow;
- a beginner manual;
- a one-shot single-image/single-color entry;
- resumable batch processing;
- a paid-call safety state machine;
- strict cache reuse;
- mandatory human review.

Its operating policy is explicit: production uses scheme B by default; scheme A requires explicit per-item review, and A+B is never run automatically. HTTP 503 is uncertain and is not automatically retried. Only HTTP 429 and a confirmed no-connection condition allow one bounded retry. A request ID is tracing metadata, not an idempotency key.

## Problems demonstrated

- Converts loosely organized image folders into deterministic N×M jobs.
- Samples and records target color with diagnostics instead of hiding preprocessing.
- Treats paid, non-idempotent image requests as transactions with an attempt ledger.
- Preserves model PNG bytes and derives delivery-friendly JPEGs atomically.
- Separates structural validation from human visual approval.
- Uses dependency injection and synthetic fixtures for offline tests.
- Turns a technically sound CLI into an operable delivery workflow for a non-technical user.

## Suggested public demo

Use synthetic or licensed images to show three subjects, for example:

1. sofa → navy;
2. umbrella → teal;
3. curtain → light gray.

Show the CLI plan, generated review page and a redacted `run-report.json`. Never publish customer inputs, credentials, real request IDs, exact token usage, internal accounting narrative or full Base64 responses.
