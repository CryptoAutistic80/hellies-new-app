# InkLift Alpha Engine

InkLift is a local-only alpha engine for testing the core sticker workflow:
turn one hand-drawn JPG/PNG/WEBP into a clean transparent PNG, a generated
cutline SVG, a preview image, and a review report.

The first version is deliberately not a hosted app. It is a private test bench
for real artwork, tuned toward faithful preservation of hand-drawn character.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .[dev]
```

Optional VTracer artwork vectorization can be installed separately:

```bash
.venv/bin/python -m pip install -e .[vector]
```

Then add `--vectorize-art` to `process` or `bench` to write optional
`artwork.svg` files when VTracer is available. Sticker alpha success does not
depend on this optional export.

## Process One Image

```bash
.venv/bin/inklift process samples/private/drawing.png --out runs/drawing-001
```

Outputs:

- `original.*`
- `normalized.png`
- `mask.png`
- `clean.png`
- `cutline.svg`
- `preview.png`
- `report.json`
- `review.html`

## Benchmark Private Samples

```bash
.venv/bin/inklift bench samples/private --out runs/first-bench
```

Private artwork belongs in `samples/private/`, which is ignored by git. Generated
runs belong in `runs/`, also ignored by git.
