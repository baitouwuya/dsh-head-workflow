<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- SPDX-FileCopyrightText: 2026 Head Workflow contributors -->

# Stationary-eye blink: reproduced adapter failures

This diagnosis concerns a fitted Smart Mesh head and the rejected exported blink
candidate. It is not a claim that the original fitted-character build fails on its
own input, or that an arbitrary head can use the original profile unchanged.
The original release tags and rejected artifacts remain unchanged.

## Independent reproduction

Three independent investigations decoded the original exported positions,
indices, morph deltas and source correspondence outside the cloud Lab. NumPy
ray intersections against the frozen source-visible aperture reproduced the
rejected full-blink result exactly: **302 / 2648 right-eye** probes and
**217 / 2654 left-eye** probes still hit eye surfaces. The neutral source exposes
every one of those probes, corroborating their frame and aperture binding.
All 50,453 original source triangles were retained in the corrected failed
candidate. Retaining topology did not establish usable deformation.

## Anatomical label correction

Subsequent independent connectivity, UV/color and component-only projection
checks confirmed an additional root cause. The prepared model's historical
`eye_surface` regions select the dark upper lash bands; its `upper_lash` regions
select the pale skin collars. The failed adapter expanded the eye partition to
include actual blue eyes and details, but retained the dark bands in the
stationary group. It therefore froze the real upper lashes and animated pale
collars instead. Anatomical labels in predecessor metadata are hypotheses, not
verified semantic correspondence.

The 5,302 historical probes are a **mixed reference**: 4,999 original first hits
are blue-eye/detail surfaces and 303 are dark lash bands. The rejected endpoint
failure remains real: 296 right and 210 left hits expose blue-eye surfaces;
another 6 right and 7 left hits expose the misclassified bands. Preserve the
original 302 / 217 measurements for comparison rather than silently relabeling
them pure-eye counts. The corrected constructor's zero-hit result over this
mixed reference proves numerical coverage of that set only. It does not prove
complete anatomical aperture coverage, semantic eye/lash assignments, or lash
attachment. The freshly inspected blue eye on one side also has 48 inherited
position-welded boundary edges; stationary behavior is not proof of closed
anatomy.

The fresh native pass independently detected this semantic error and derives a
new input-bound classification. Its actual exported result still needs its own
handoff. Local diagnostic proof must not be promoted into native acceptance.

## Geometric and measurement defects

The following defects were isolated rather than inferred from a test score.
Items 1, 2 and 5 explain the exported skin-warp candidate. Items 3 and 4 were
reproduced in a separate diagnostic of the proposed surface-recipe replacement;
the cancelled native surface-construction pass returned no artifacts.

1. **Unweighted depth projection.** The adapter disabled neutral rim fitting but
   retained a clearance clamp independent of blink weight. Calling its geometric
   function at zero moved source points by as much as 0.050633 model units.
   The exported controller interpolates continuously from Basis to the first
   sample, so this is not a literal discontinuity in the exported animation.
   Instead, almost all of that depth displacement occurs by the quarter-blink
   sample. Removing only the clamp reduces quarter-blink normal reversals from
   35 to zero and maximum head displacement from 0.050585 to 0.010706. Full
   closure still fails, with exposed-eye counts increasing to 331 / 264. A
   weight-dependent clamp fixes the zero-value contract but is not a closure fix.
2. **Masks split original lash geometry.** The edited vertex mask cuts across
   connected source lash triangles. One endpoint moves while its neighbor stays
   fixed. The worst measured source lash edge stretches 51.51 times; a second
   side reaches 48.84 times. Whole-component classification and coherent
   deformation are required; merely counting moving lash vertices is inadequate.
3. **Rim samples violate the surface recipe's contour contract.** The frozen
   profile alternates lower and upper samples at successive lateral positions.
   The surface recipe expects a cyclic, simple closed contour. Treating the
   alternating array as a Catmull-Rom contour produces a zigzag. An explicit
   lower-chain/upper-chain assembly reduces a diagnostic hood's exposed-eye
   probes from 1462 / 1498 to 4 / 5 with otherwise identical fitted parameters.
   Those remaining corner misses mean contour ordering alone is not a pass.
   Some left-side sampled columns also have identical upper/lower points inside
   the aperture, creating a pinched, self-touching loop even after reordering.
   A conservative construction envelope must be fitted separately; the frozen
   acceptance probes must not be changed to make that envelope pass.
4. **The affine sphere does not bound the actual eye fronts.** With the ordered
   contour and the small nominal clearance, the diagnostic hood still exposes
   1378 / 1357 probes. A single largest-residual clearance moves unrelated points
   too far forward. Sampling actual eye depth only at surface vertices is also
   insufficient: interpolated triangles can cross the obstacle between them.
   The construction must use a conservative measured obstacle and check the
   resulting triangulated surface, not assume the proxy establishes clearance.
5. **Keyframe-only validity misses real collapse.** The existing neutral,
   quarter, half, three-quarter and full samples miss four newly collapsed
   original lash triangles between samples. The reproduced control values are
   approximately 0.01485, 0.01621, 0.02901 and 0.03158. Triangle double-area along
   linear vertex interpolation is the norm of a quadratic vector; its squared
   norm is quartic. Checking its interior extrema detects these collapses.

## Interpreting the gates

The 67 endpoint world-normal reversals reproduce exactly, but a negative dot
product against the neutral normal alone does not prove inversion: a valid
rigid rotation can produce it. Report this orientation diagnostic separately
from zero-area collapse, continuous morph validity and measured intersections.
Do not discard the real closure failures or visible skin/lash distortion when
correcting this metric.

Closure must name the first-hit surface class. A lash-only hit is not proof of
real eyelid closure. Use the frozen, input-bound aperture and permitted lid/skin
occluders, report eye hits, empty rays and lash-only hits separately, and match
the actual material sidedness. Frontal sampling does not prove all-angle
collision freedom or visual quality.

## Retry boundary

The next native Lab starts from the accepted incoming head, not a rejected
candidate or its deformed neutral surface. It clones the corrected repository
revision supplied by runtime configuration, verifies the obtained commit and
runs both repository test suites. It constructs actual eyelid surfaces from
explicitly classified chains, preserves stationary eye appearance and protected
source geometry, and maps original lashes by connected geometry. Its generic
prompt must call the tested construction and audit helpers rather than ask the
Lab to invent another repair algorithm.

Local diagnostic geometry is never uploaded as the pipeline result. Native
construction, export/reimport, matched textured renders and the narrow handoff
remain required. Gaze remains unsupported; cosmetic polish and later mouth or
expression stages are outside this construction pass.
