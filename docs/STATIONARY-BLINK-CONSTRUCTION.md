<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- SPDX-FileCopyrightText: 2026 Head Workflow contributors -->

# Measured stationary-eye lid construction

Read [the reproduced diagnosis](STATIONARY-BLINK-DIAGNOSIS.md) before adapting
another head. Use the incoming model in a documented common frame: X is depth
toward the viewer, Y is lateral and Z is up. These are source-only geometry and
audit helpers, not an automatic anatomical landmark detector.

Treat predecessor anatomical region names as unverified. Cross-check connected
geometry, original UV/texture appearance and component-only views before
assigning eye, lash and skin roles. In the diagnosed input, inherited eye labels
selected actual lash bands while inherited lash labels selected pale collars.
Do not place true lashes in the stationary-eye obstacle set. Report separately
any source eye boundary openings and any ambiguous semantic assignments.

```python
from lab_recipes.aperture_contract import (
    construction_envelope_from_samples, rim_from_upper_lower_chains,
)
from lab_recipes.lid_surface import build
from lab_recipes.triangle_depth_bound import TriangleDepthBound

# Prefer measured anatomical upper/lower chains when actually available.
# Otherwise explicitly fit a conservative construction envelope. It is not an
# anatomical attachment claim and must not replace frozen acceptance probes.
fitted_eye['rim_xyz'] = construction_envelope_from_samples(visible_eye_samples)
parameters = dict(input_fitted_parameters)
parameters.update(linear_contour=True, conservative_envelope=True,
                  uniform_cross_section=True)
depth = TriangleDepthBound(actual_stationary_eye_triangles)
evaluate, faces = build(fitted_eye, upper=True, d=parameters,
                       triangle_depth_bound=depth)
```

Repeat for lower and opposite-side lids. Fit all dimensions to the input; do not
reuse another head's indices or measured coordinates. Cross-section sample count
must be a multiple of four in uniform mode to include exact fixed outer anchors.
The existing three-argument API remains supported for valid fitted profiles.

`TriangleDepthBound` returns the maximum source-triangle X over each intersecting
projected triangle bounding box. False-positive box overlap increases clearance;
it cannot underestimate the triangle's depth. The recipe computes each lid
triangle's full control-range footprint once and propagates its bound to incident
vertices. Uniform cross-section sampling makes the Y/Z trajectories affine, so
the endpoint union bounds the sweep. Static bounds preserve the shell offsets
and fixed outer anchors. A changing per-pose bound can move those anchors.

An empty obstacle footprint is an explicit negative-infinity result and uses
the existing proxy fallback. Record `depth.last_empty_footprints`; a fallback
inside the visible aperture needs explanation and independent coverage checks.
Point-depth samples alone do not bound the triangles interpolated between them.
NaN, positive infinity, malformed callbacks and invalid control values are rejected.

`linear_contour` avoids Catmull-Rom overshoot. `conservative_envelope` prevents
smoothing from moving section bounds inward. `uniform_cross_section` avoids
highly clustered vertices on thin ellipses. These options do not establish
anatomical attachment, visual quality or all-angle collision freedom.

## Exported-controller checks

Use `lab_recipes.blink_handoff` on the actual reimported geometry:

- `audit_neutral_and_near_neutral`: evaluate the shipped controller at zero,
  small positive values and the configured samples; require neutral identity.
- `audit_component_binding`: report partial source lash components, moving/static
  edge cuts, edge strain and duplicate seam consistency. Canonical IDs require
  an explicit runtime tolerance and must be real nonnegative correspondence;
  omit them for generated/unmapped geometry rather than using a shared sentinel.
- `audit_linear_morph_segments`: check interior triangle-area extrema between
  every adjacent actual LINEAR controller knot. Supply model-scale source-area
  and relative collapse tolerances. Empty geometry or no source-valid faces is
  an error, not a passed audit. This does not certify nonlinear controllers or
  arbitrary combined morphs from sparse endpoints.

World-normal rotation is diagnostic only. Keep real collapse, intersection,
closure and appearance checks separate. Count real lid/skin first hits, eye
hits, empty rays and lash-only hits separately using unchanged input-bound
probes and the actual material sidedness. Preserve original eye appearance,
source triangles, image bytes and unrelated controls. Original lashes must
follow their corresponding lids coherently without cutting an edit mask through
connected source geometry.

The integrated constructor reproduced zero full-closure misses on 5,302 frozen
mixed-reference probes (4,999 eye/detail and 303 lash first hits), zero float32
degenerates, zero fixed-anchor movement/reset error
and zero continuous-interval collapses. All first hits were generated lid
surfaces; rejected added globes were excluded and original source correspondence
was checked exactly. This is not proof of a complete anatomical aperture or
correct semantic eye/lash partition. These are numerical construction results
only. The fresh native retry passed closure and collapse checks but failed
appearance, source-skin attachment and lash deformation. Its per-vertex nearest
UV transfer crossed unrelated atlas regions, fixed recipe rows were not bound
to skin, and whole-component displacement still stretched lashes excessively.
See the diagnosis for measured results. Before another native construction,
validate coherent texture transfer, actual skin binding and shape-preserving
lash attachment outside the Lab. The bound helper does not implement those.
