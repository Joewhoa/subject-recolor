# Public Furniture Test Evaluation Protocol

## Approved paid scope

- Input: `kubus_sofa.jpg`
- Target: sofa leather/upholstery only
- Color card: `deep_teal.png`, target `#2F6B63`
- Model: `gpt-image-2`
- Approved new paid calls: **1**
- Hard cap: **1**

## Automated checks

After a result exists, run:

```bash
subject-recolor evaluate \
  --workspace examples/public-furniture-test/workspace \
  --date 2026-09-03 --inputs kubus_sofa --cards deep_teal
```

This writes `output/evaluation.json` with:

- artifact/cache validity;
- exact source and result dimensions;
- mean absolute luma difference;
- changed-pixel ratios at two thresholds.

These are mask-free global diagnostics. They can detect no-op results, massive redraws or size changes, but cannot prove that only the sofa changed.

## Manual acceptance rubric

Score each item 0–2, for a total of 12:

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Subject coverage | large leather regions missed | small regions missed | complete sofa coverage |
| Target-color fidelity | wrong family | broadly teal with drift | convincing deep teal under lighting |
| Material preservation | leather/tufting lost | minor smoothing | leather highlights, seams and tufting preserved |
| Background stability | obvious redraw | small local changes | windows, walls and floor unchanged |
| Edge quality | severe halos/bleed | small artifacts | clean sofa boundaries |
| Composition/geometry | changed | minor deformation | unchanged |

Suggested interpretation:

- 10–12: portfolio-quality candidate;
- 7–9: usable with limitations and documented failure cases;
- 0–6: prompt/model path requires revision.

## Test result

Status: **Executed successfully — one approved call, no retry.**

- Request model: `gpt-image-2`; response model: `gpt-image-2-codex`.
- Request ID: **redacted**; request identifiers are tracing metadata, not idempotency keys.
- Source: 1587×893 JPEG; result: 1672×941 PNG; aspect ratio preserved.
- Token usage: **redacted**.
- Strict cache validation reported `complete`; the unchanged task was recognized as already satisfied.

### Manual review score

| Dimension | Score | Observation |
|---|---:|---|
| Subject coverage | 2/2 | All visible leather upholstery was recolored, including tufted seat, back and arms. |
| Target-color fidelity | 2/2 | Result is a convincing deep teal while highlights and shadows vary naturally around the target reference. |
| Material preservation | 2/2 | Leather sheen, seams, piping and tufting remain clear. |
| Background stability | 2/2 | Windows, wall, floor, legs and room composition appear stable in side-by-side review. |
| Edge quality | 2/2 | Sofa boundaries are clean with no obvious teal bleed or halo at normal review scale. |
| Composition/geometry | 2/2 | Sofa structure, perspective and layout remain consistent; output resolution changed but ratio did not. |

**Total: 12/12 — portfolio-quality smoke-test candidate.**

This is a visual judgment on one clean single-subject image, not proof of performance on the harder multi-sofa showroom image. Mask-free diagnostics report mean absolute luma difference and changed-pixel ratios, but cannot independently prove background invariance.

### Public safety interpretation

The published evidence is intentionally limited to observable evaluation facts. Real request IDs, exact token usage and internal accounting or reconciliation narrative are redacted. A request ID is useful for tracing only and must not be treated as an idempotency key.

For the later production-delivery workflow, scheme B is the default. Scheme A requires explicit per-item human review, and A+B is never automatic. HTTP 503 is classified as uncertain and is not automatically retried. Only HTTP 429 and a confirmed no-connection condition permit one bounded retry. Human review remains required before accepting generated delivery assets.
