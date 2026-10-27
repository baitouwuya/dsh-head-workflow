<!--
SPDX-License-Identifier: GPL-3.0-or-later
SPDX-FileCopyrightText: 2026 Head Workflow contributors
-->

# Eyes and gaze: measured limit on a shallow SM head

The v0.1.2 recipe covers **stationary eyeballs plus left/right blink**. It does not cover
gaze: there is no gaze stage, and `head_repair/` contains no gaze planner. The scleral
globe and eye-integration work lives in `research_stages/scleral_globes.py` and
`research_stages/sm_eye_integration.py`, which are research scripts rather than a stage
with an acceptance gate.

## Observed failure

A canvas Lab attempted "eyes and gaze" on the trimmed canvas input: a Smart Mesh head with
shallow eye sockets, one of the VRoid-style parts rather than the full character. The Lab
built stationary eyeballs, fitted pivots and separate iris components, and then measured
gaze. Its own report:

| Measurement | Result |
| --- | --- |
| Worst aperture coverage across 18 gaze samples | **66.12 %** |
| Degenerate iris triangles | 1 |
| Protected-face movement | 0 |
| Neutral reset error | 0 |
| Image bytes | preserved |
| Primary model | withheld |

Rotating a shallow source eye surface exposes dark gaps around the iris, so more than a
third of the aperture is uncovered at the worst direction. The Lab refused to hand off a
primary model, which is the intended behaviour: the gate is a refusal mechanism, not a
score.

## Gate definition used

Aperture coverage is the fraction of the eye opening that still shows sclera, iris or eyelid
geometry rather than the interior, sampled over a fixed set of gaze directions. Report the
worst case; never fill a missing sample with zero. A stage that cannot reach a usable worst
case records the number and hands off nothing.

## What is required before gaze becomes a stage

1. A fitted-globe builder that closes the socket volume, not just a rotated disc.
2. Iris surfaces welded to the globe rather than floating in front of it.
3. A gaze sweep with the coverage gate above, run on every candidate.
4. An explicit rule for how far the eye may rotate before the aperture gap is visible.

Until then the chain treats eyes-and-gaze as **known limitation**, keeps stationary eyes
and blink as the delivered step, and does not spend a stage on an unbounded repair loop.
