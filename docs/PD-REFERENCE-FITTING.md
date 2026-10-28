# Normalized PD reference fitting

**Preferred lid-motion reference:** the operator's native VRM `blink` is now
available as `profiles/reference/base-vrm.json`. It improves closure over the
F00 Joy surrogate. See [native VRM findings](BASE-VRM-FINDINGS.md) for the live
PD compatibility result, reproduction steps, and remaining geometry limits.
The F00/M00 workflow documented below remains available and unchanged.

This independent module reduces private F00/M00 template anatomy to normalized
curve coefficients and statistics. It does not run the canvas driver, change an
existing construction profile, register the PD UI, create Blender objects, or
export a reference mesh. The installed Parametric Deformation adapter performs
the reference evaluations. NumPy performs fitting; no SciPy dependency is needed.

## Deliverables

- `profiles/reference/F00.json`, `M00.json`: bilateral aperture, five lid-margin
  poses, lash-sheet centreline and anchor offsets, and measurement statistics.
- `profiles/reference/F00-fit.json`, `M00-fit.json`: fitted reusable lid models.
- `profiles/reference/host-verification.json`: live Blender parameter-recovery
  results and scene-preservation check.
- `head_workflow/reference/`: extraction, normalization, solvers, and an opt-in
  adapter for `lab_recipes/lid_surface.py`.
- `tests/test_reference.py`: synthetic geometry, real normalized profiles,
  nonlinear/bounded fitting, and existing lid-builder parameter recovery.

The private pack files, meshes, vertex indices, UVs, textures, materials, and
evaluated world coordinates are not included. Provenance hashes identify the
private evaluation inputs and installed add-on code without distributing them.
The coefficients describe derived curves, not a vertex-for-vertex reference
copy. Do not commit private packs or evaluated mesh dumps when regenerating.

## Measurement contract

The source `face` mesh is evaluated through
`VRoidAdapter.load(load_pack(...))` and `VRoidAdapter.evaluate(params, {})`.
Region slot labels are used privately to locate the skin, sclera, and lash
sheet. No material is imported. The skin eye boundary must geometrically match
the sclera boundary within `1e-5` Blender units; ambiguous or non-manifold
boundaries fail extraction. Vertex IDs are discovered from topology, not stored
in the public profile.

For each side, the neutral medial and lateral canthi determine the origin,
axes, and scale:

- Origin: neutral canthus midpoint.
- Scale: neutral 3D canthus distance (one unit).
- Coordinates: medial-to-lateral, orthogonalized up, outward depth.
- The frame stays fixed throughout the blink. Reflection canonicalizes the two
  sides; `positive_x`/`negative_x` refer to PD output coordinates, avoiding an
  assumed anatomical naming convention after the pack's mirror conversion.

The upper and lower margins are parameterized separately by their **neutral**
arclength. `u=0` is medial and `u=1` lateral. Both endpoints are constrained in
the curve regression. Equal `u` on the two lids is not necessarily equal lateral
position. Compare closure by lateral cross-section, not by subtracting equal-u
heights. Pose weights are exactly `[0, .25, .5, .75, 1]`.

The available expression is `F00.Eye.Joy` / `M00.Eye.Joy`, discovered by name;
these are **closure surrogates**, not independently captured physiological
blinks. The F00 surrogate overlaps at full weight. M00 has both a residual
opening and local overlap. Neither target certifies collision-free closure.
The fitter preserves those differences instead of silently fabricating a
closed target. Neutral geometry is nearly identical between these pack versions;
their closure expressions differ.

The lash centreline is the midpoint of the two boundaries of the geometric
lash sheet, paired by neutral boundary arclength. It includes the untextured
sheet extensions. It is **not the visible alpha-cutout lash contour**. The
same `u` on the upper lid anchors the band in every pose. The local tangent is
the upper-margin derivative; the normal is projected +depth; binormal is
normal cross tangent. These local frames are orthonormal and right-handed.
`anchor_offsets` are curve regressions of coordinates in these moving frames.
For exact attachment to the *fitted* model, use the offsets and frames returned
by `evaluate_lid` together, rather than mixing them with reference-model frames.

Margins use degree-eight Chebyshev series on `x=2*u-1`. The lash centreline and
anchor offsets use eight continuous segments of degree four; each segment maps
its interval to `[-1,1]`. Coefficients have axes `[coefficient, coordinate]` or
`[segment, coefficient, coordinate]`. `curve_points` implements both formats.
Every reduction includes RMS and maximum 3D error, in eye-width units, against
65 derived source samples. Coefficients are rounded to seven decimals.
Continuity at segment boundaries is C0; lash tangent continuity is not promised.

### Depth and thickness: what the packs actually support

`socket_depth.statistics` summarizes adjacent-skin depth minus margin depth
over unique directed collar edges, divided by neutral eye width. Positive is
a margin recessed behind its neighboring skin. This is a **local collar-recess
proxy**, not depth to an anatomical socket floor; `anatomical_socket_depth` is
null. Statistics include minimum, median, mean, p95 and maximum.

The skin is an open sheet without paired inner/outer lid surfaces.
`lid_thickness.physical_thickness` is consequently null. The profile includes
the same statistics for collar-edge lengths under `collar_edge_length_proxy`;
these depend on the source tessellation and must not be interpreted as physical
thickness. Shell construction requires a caller-selected thickness. This is a
limitation of the supplied anatomy, not a missing guessed default.

## Use without the private packs

From the repository root with Python and NumPy:

```sh
python tools/fit-reference.py profiles/reference/F00.json --output build/F00-fit.json
# An explicit design choice, in eye-width units:
python tools/fit-reference.py profiles/reference/F00.json --output build/F00-solid-fit.json --shell-thickness 0.012
python -m unittest discover -s tests -v
node --test tests/verify-glb.test.cjs
```

```python
import json
import numpy as np
from head_workflow.reference.fit import fit_lid_profile, evaluate_lid

reference = json.load(open('profiles/reference/F00.json'))
model = fit_lid_profile(reference, degree=6, shell_thickness=.012)
pose = evaluate_lid(model, 'positive_x', blink=.375, u=np.linspace(0, 1, 65))
# pose: upper/lower margin, lash, anchor_origin, anchor_axes, anchor_offsets
# To place any normalized point q in an explicitly chosen target frame:
# world = origin + eye_width * q @ axes
```

The compact fit solves endpoint-constrained least squares for every margin and
lash curve at all five weights. It carries measured scalar statistics through
unchanged; it does not turn a proxy into a thickness estimate. Intermediate
weights interpolate adjacent fitted poses, rather than summing absolute shapes.
With the bundled profiles, fitted-curve RMS is about `0.00097` eye widths for
F00 and `0.00116` for M00; maximum additional fitting error is under `0.0049`.
Source reduction adds up to `0.00642` for margins and `0.00419` for lashes.
These are separate error stages, not a claim of exact reference reproduction.

## Fit the existing canvas lid construction

`fit_canvas_lids(eye, target_eye, settings, bounds)` evaluates the existing
rounded-shell recipe in memory and solves selected settings against all five
target margins. Settings stay in the builder's metre units; residuals are
normalized. It uses the neutral aperture frame of the supplied canvas eye and
samples the inner shell ring at `phi=3*pi/2`. Use at least three length segments
and a cross-section count divisible by four.

```python
from head_workflow.reference.canvas import fit_canvas_lids

result = fit_canvas_lids(
    eye, reference['eyes']['positive_x'], settings,
    {'closure_height_fraction': (-.6, .6),
     'upper_closure_depth_offset_m': (-.002, .002)},
    max_iterations=30, tolerance=.002,
)
# result['settings'] is a candidate; nothing is written to the canvas.
```

Supply the canvas construction's own full settings dictionary. The neutral
aperture remains the input `eye['rim_xyz']`; these two closure controls cannot
reshape it. A mismatched aperture, fixed globe, or insufficient parameter family
will leave residual error. Inspect `rms`, `max_abs`, `status`, `accepted`,
`jacobian_rank`, `at_bound`, and the descending objective `history` before use.
`accepted` means the requested numerical RMS tolerance was reached, not that
the construction passes collision, attachment, or visual checks.

The shell recipe has no lash builder. An optional
`lash_evaluator(candidate_settings, weights, u)` can supply normalized `(5,65,3)`
centrelines and include lash residuals in the solve; otherwise `fitted_features`
explicitly says only `lid_margin`. The fitted profile's lash anchor frames and
offsets are available for the other pipeline to attach its own band. An arbitrary
new constructor can use `bounded_fit` with its own measurement callback.

## Regenerate and verify through the required host bridge

Run in guest PowerShell from this clone:

```powershell
& tools/run-pd-reference.ps1 -OutputDirectory profiles/reference -VerifyFit
```

The default host directories are the supplied PD add-on, F00 and M00 locations;
all three can be overridden by named parameters. The wrapper sends source code
through exactly `C:\ProgramData\dsh\hostcap\blender-call.ps1 -File <script.py>`.
It does not start another Blender or access the host through an alternate
execution route. Private pack arrays stay in host memory. Only normalized JSON
returns to the guest. Temporary source-only requests go into ignored
`.reference-work/`. No `.blend`, image, mesh, texture, or material is saved.

`-VerifyFit` evaluates targets at `Eye Size Y=.25`,
`Outer Eye Slant (Y)=-.2`, starts at zero, and solves the installed PD controls.
The objective contains both lids and lashes across both sides and five weights,
plus the mean/median/p95 collar-recess proxy. It respects the supplied bounds.
Live Blender 5.2 checks recover both controls to within `3e-5` for both packs.
This is a two-control recovery check, not certification of all PD sliders.
Global size is deliberately removed by normalization, so uniform-scale controls
can be unidentifiable; inspect Jacobian rank.

The host check records active scene, frame, selection, per-scene object counts,
and mesh/material/image counts before and after. No operator modifies a scene.

## Baseline and scope

Based on repository commit `352590cb12178ff2ef91fb76e51b6067fa89e0cb` in a fresh
clone. The original six Python tests and all four `verify-glb` Node tests pass.
The new suite adds eighteen Python tests. A wider baseline run of
`node --test tests/verify-glb.test.cjs driver/tests/*.test.cjs` has six pre-existing
failing files: `destination-append`, `driver-runtime`, `driver`, `observer`,
`representative-recovery`, and `ui`. Missing driver modules and older UI test
expectations cause those failures in the untouched checkout. This branch does
not change those driver files. No canvas UI, other checkout, or other chat was
used or modified.
