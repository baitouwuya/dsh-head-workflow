<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- SPDX-FileCopyrightText: 2026 Head Workflow contributors -->

# Visual failure reproduction and the next native check

The last native construction passed frontal closure and continuous triangle-area
checks but failed the handoff. Preserve its evidence; the following numerical
corrections are not a claim that a replacement model has passed visual review.

## Striping: appearance coordinates and winding

Independent nearest-vertex UV transfer interpolated across unrelated atlas
regions. Of 97,280 sampled generated-triangle points, 2,435 departed from the
corner-color range and 458 became dark despite bright corners. The generated
upper closed cores also had inward winding. A software lighting comparison with
only winding corrected reduced dark generated pixels from 19,707 to 188 of
36,463. This reproduction uses approximate lighting, not the native renderer.

`skin_appearance` transfers measured source skin colors to linear vertex colors
on a new texture-free material. Original encoded images, UVs and material
bindings stay intact. Geometry attachment samples and clean skin-color samples
serve different purposes: the original skin contains baked eyeliner. Boundary
colors are retained and blended into an independently sampled clean interior.

`lid_surface.build` now orients its generated closed core outward. `lid_normals`
separates closed cores from open transition strips, builds explicit normals and
normal morph targets, and checks analytic between-knot normal cancellation.
The diagnosed input has zero cancellation, but maximum interpolation error near
some caps remains about 46 degrees. Unit normals alone do not certify shading.

## Detached anchors: fixed position is not attachment

The rejected candidate had 388 fixed vertices described as anchors. None lay
within the declared source-skin tolerance; the maximum gap was 0.0641269 in the
measured frame. Projecting only vertices still left unsupported boundary edges.

`skin_attachment`, `surface_routes`, `source_paths` and `skin_transition` bind
the entire fixed boundary to actual source triangles. The final diagnostic
certificate covers all 449 boundary segments within 0.000001; the largest
vertex gap is about 0.00000001355. Only vertices with identical complete motion
trajectories are welded. Newly generated faces may never be excluded as inherited
degenerates. The tested correction has no new degenerates or continuous LINEAR
collapses. Attachment is measured again after float32 export and reimport.

`eye_clearance` applies constrained measured projected-triangle clearance after
attachment, preserving the skin boundary and moving inner rail. Frozen aperture
probes include visible eyes and the back-facing head visible through the socket;
that back wall is not a valid closure occluder. The final diagnostic has zero
exposed targets on 4,085 right and 4,028 left actual-aperture probes. A historical
skin-superset probe set is reported separately. Empty meshes, empty constraints
or empty probe sets cannot count as a pass.

## Lash stretching: contact roles and shape preservation

Whole-component displacement still stretched a source edge 3.446875 times.
Neutral proximity alone incorrectly classified moving rail contacts as static
skin roots. `lash_contacts`, `lash_transfer` and `anchored_lash` separate actual
static canthus/wing contacts, coherent moving inner-rail contacts and incidental
back-wall overlaps. Rigid local transfer plus constrained relative-edge ARAP
preserves the original complete components and their canonical seams.

Measured maximum edge expansion falls to 1.381931 on the right and 1.500671 on
the left; minimum ratios are 0.751753 and 0.800048. Actual static, dynamic and
accessory carrier gaps are at most 0.0016405 against the input-derived 0.00173065
limit. No protected geometry or stationary eye moves, and no new continuous
collapse occurs. These are improvements, not a claim of perfectly rigid lashes.

## Native verification still required

The combined software preview retains ribbed/scalloped shading and original
baked ink above the closing band. A native visual pass remains unproven. Use the
existing Smart Mesh input directly, inspect its original polygon/UV-corner
structure, and derive all correspondences again. Its direct native input may be
an unrigged FBX. Reconnecting it does not itself repair the geometry.

Run the matched renderer only inside the Lab's supplied current Blender; do not
download, install or execute Blender on the operator's VM. Record the actual
runtime. Reimport the sealed candidate and verify explicit normal targets,
vertex colors/materials, skin or rigid-parent binding, independent controls and
unchanged input image bytes. Compare native source/candidate views and deliberate
shading ablations. Withhold the primary asset if attachment, striping or lash
deformation remains visibly unacceptable, even when numerical coverage passes.

See [the native verification contract](NATIVE-BLINK-VERIFICATION.md). Exactly one
fresh native construction pass follows this diagnosis. Local diagnostic meshes
are evidence only and are never uploaded as pipeline outputs. Gaze remains a
known unsupported capability.
