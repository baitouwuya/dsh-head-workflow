<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- SPDX-FileCopyrightText: 2026 Head Workflow contributors -->

# Full-look motion precheck source

These files are source only. The parent runs the authorized host Blender; no VM
Blender is installed or executed. Host output is diagnosis, never the final native
asset or final acceptance. The Lab must rebuild from its connected input using the
repository, export/seal its own model and render that actual reimported model.

## Runtime request

Fill `full_look_request.template.json` with actual host paths, measured source scale,
knots, object/material roles, cameras and lights. The example paths/roles describe
the current measured cache contract; a new input must supply its own values.
Camera/light coordinates are in the original source world frame. `source_scale`
is measured by the boundary construction, not guessed from file names.

- The input BLEND is the source-only native inspection scene, not the failed amber
  diagnostic scene. The source mesh is selected by vertex count and measured world
  correspondence, never a fixed object name or component number.
- `source_npz`: `vertices` in original Blender world coordinates; `faces` in its
  original vertex ordering; `triangle_loops`, `uv_0`, `loop_vertex_ids`,
  `loop_normals_local`, `triangle_material_ids`, `component`.
- Each lid prefix supplies `_poses[K,N,3]`, `_faces`, `_face_domains`,
  `_skin_boundary_vertices`, `_inner_rail_vertices`,
  `_source_sample_triangle_ids`, `_source_sample_barycentric`.
- Each source control supplies poses `[K,source_vertex_count,3]` and rotations
  `[K,source_vertex_count,3,3]` through runtime-configured keys. Both are normalized
  world-frame data: positions multiply by `source_scale`; rotations remain world
  rotations. Neutral must match the measured source. Bilateral motion combines
  independent source deltas; unrelated original morphs are not reset.
- Source delta vectors convert through the actual source object's inverse world
  matrix before shape-key assignment. Source loop normals remain their original
  neutral local values; Blender evaluates shape-key normal compensation once.
  Inherited zero custom-normal sentinels are preserved and counted. Supplied
  rotation arrays are available for isolated static-pose diagnosis, not written
  onto the undeformed Basis on every frame.

## Full appearance and source preservation

`assemble()` loads the input through a new library scene and creates a separate
review scene. It never resets or deletes existing host scenes and never overwrites
the source BLEND. The original textured source mesh is copied for review, preserving
its UVs/materials and packed image data. A separate Non-Color decoder image reads
the original encoded bytes; the source image colorspace/material is not changed.

The existing `skin_appearance` and `lid_normals` helpers provide coherent source-skin
color values and separate shading domains. The compatibility mode retains exact
boundary colors; the optional clean mode releases that pigment constraint. Generated lids use linear vertex color and an actual skin material, not
amber diagnostic material. Whole original lashes receive the supplied deformation.
Per-input component/material roles are read from runtime files. Numerical reports
and normal warnings remain diagnostics; visual motion review decides suitability.

## Host invocation and bounded rendering

Put this directory on the authorized host Python path, then call:

```python
import full_look_review
result = full_look_review.assemble(request_path)
session = result['session_id']
full_look_review.render_batch(session, 'bilateral', 'front', [0, 6, 12])
# Then render every requested frame, angle and independent/bilateral scenario.
```

Use frame subsets for bounded tool calls. Do not repeat already rendered frame
indices unless an explicit new diagnostic run/output folder is used. Every frame
is visibly stamped with scenario, view, frame and control values. The complete
13-frame cycle closes and reopens, including between-knot samples. Render all three
angles for independent left, independent right and bilateral motion; a single full
closure frame is insufficient. `full-look-review.json` records frames, original
image hashes, source-file preservation, runtime version and diagnostic qualifications.

The scene uses in-memory controls to create review sequences. This alone does not
prove an exported animation. In `native_stage_build` mode the Lab may call
the native export and cycle-verification helpers described in
`NATIVE-FULL-LOOK-EXPORT.md`. They seal and reimport its own model, decode the actual
serialized weight clips, and render matching close/reopen states and videos. Never copy host geometry, NPZ or color arrays
into the native job; only reusable source/configuration may be reused. The Lab's
own exported asset and its own rendered motion are the final visual evidence.
# Optional clean skin appearance mode

Set `appearance.visual_color_mode` to `low_frequency_skin` for the next visual
review. Omission retains `measured_boundary` behavior for compatibility. The new
mode fits one shared robust affine YZ skin-color field per eye side from actual
source-skin triangle samples outside the eye/lash exclusion region. Samples are
spatially balanced, dark/chroma outliers are rejected, and predictions are bounded
by retained reference quantiles. Upper and lower lids use the same field at the
same coordinates. No boundary colors are forced to retain painted eyeliner.

The report records reference variance, removed dark/color outliers, field
coefficients, output bounds and changes from direct source-bound colors. Rejected
samples are appearance outliers, not a certified semantic pigment segmentation.
The mode changes only generated lid colors; original encoded image bytes and
source materials remain unchanged. Static original pigment, occlusion and lid
geometry can still be visibly wrong. The rendered motion decides whether this
appearance is useful; numeric diagnostics do not accept the result.
