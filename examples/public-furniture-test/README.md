# Public Furniture Smoke Test

A two-image, one-color-card evaluation set for Subject Recolor:

- one clean single leather sofa;
- one difficult showroom containing multiple sofas and mixed wood/upholstery construction;
- one deterministic color card, deep teal `#2F6B63`.

See `ATTRIBUTION.md` before publishing source or generated images. Both photographs are CC BY-SA 3.0 and edited outputs must follow the ShareAlike terms.

Run the free preflight:

```bash
subject-recolor doctor --workspace examples/public-furniture-test/workspace
subject-recolor plan --workspace examples/public-furniture-test/workspace --date 2026-09-03
```

For the recommended first paid smoke test, use only the clean image:

```bash
subject-recolor plan --workspace examples/public-furniture-test/workspace \
  --date 2026-09-03 --inputs kubus_sofa --cards deep_teal --json
```

After explicitly confirming the reported call count:

```bash
subject-recolor run --workspace examples/public-furniture-test/workspace \
  --date 2026-09-03 --inputs kubus_sofa --cards deep_teal \
  --expect-calls 1 --max-paid-calls 1 --yes
```

The multi-sofa image should be run separately as a harder second test so a failure is attributable and costs remain controlled.
