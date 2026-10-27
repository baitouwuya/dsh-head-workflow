<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- SPDX-FileCopyrightText: 2026 Head Workflow contributors -->

# Exterior skin continuity

The direct-input native attempt had 14 unsupported boundary segments out of 96,
despite a maximum vertex-to-skin gap of 1.4347545032405242e-8. Host Blender
5.2.0 LTS reproduced those values from the preserved native source arrays.

The fatal segment exposed a fitting error. Nearest 3D skin binding selected an
endpoint 0.0242695 behind the frontmost source skin. Expanding the routing domain
found a genuine source-surface path around a fold, but that path retained the
hidden-layer attachment. It was rejected. Increasing path length alone is not
the correction.

## Tested construction path

Use `tools/build_exterior_lid_boundaries.py` with runtime `--source`, `--probes`,
`--configuration`, `--roles`, `--repository` and a new `--output` directory.
The source arrays contain measured vertices, faces, connected-component roles
and corner correspondence. The role file is fitted to the actual input; no
component numbers or vertex coordinates from another head are built into the
entry point. Frozen probe groups must match the runtime eye-role names. The
entry point preserves input files, records their hashes and refuses an existing
output directory.

The entry point calls `exterior_skin_boundary.fit_exterior_skin_boundary` for
both upper and lower lids. This wrapper always requires the exterior predicate;
there is no option to omit it. It:

- Finds candidate skin faces in an input-scaled local region and tests their
  projected visibility against the complete source skin domain.
- Fits outer anchors to an exterior sheet, allowing bounded lateral/vertical
  movement while preserving the moving inner rail.
- Welds only generated vertices with identical complete motion trajectories.
- Checks whole boundary segments for source contact, frontmost skin support and
  conservative aperture exclusion. A direct chord that passes proximity but
  fails exterior visibility is routed onto the surface instead of accepted.
- Certifies routed and final float32 edges at the unchanged attachment tolerance.
  A projected bounding-box rejection prevents a remote near-edge-on triangle
  from becoming a numerical false occluder.

The routing cap remains an explicit runtime limit. The measured correction did
not enlarge the original cap or change the source mesh. `boundaryFit` in the
configuration supplies the normalized refit and routing limits; the entry point
records actual movement and the required route length.

Returned `construction_to_final_vertex_ids` composes both generated weld stages.
Use it when mapping original construction attributes. The separate
`post_initial_weld_to_final_vertex_ids` describes only the later mapping. Use the
returned `inner_rail_vertices`, source-triangle/barycentric samples and
`face_domains`; never reuse old ring indices after topology changes.

## Measured host result and limits

All four host-constructed boundaries pass: 95, 114, 103 and 109 complete segments
(421 total). New neutral/knot degeneracy and continuous LINEAR collapse are zero.
The largest inner-rail difference is 1.49e-8 from float32 encoding. The largest
reported upper-lid refit is 0.04674 in 3D and 0.03225 laterally/vertically, within
the declared 0.06083 and 0.04055 limits in the normalized frame. Every required
route remains below its original length cap. These values describe this fitted
input and are not acceptance counts to copy onto another model.

`fixed_strip_contact.audit_fixed_core_strip_contact` checks the complete contact
between transition strips and fixed original core edges. Each subdivided contact
edge lies inside the tolerance capsule of a real core edge; reverse coverage
checks for gaps. Both sides remain exactly fixed at the controller knots, so the
certificate extends across the complete LINEAR intervals. The measured maximum
bidirectional contact bound is 4.93e-8, below 1e-6.

These are geometric T-junction contacts, not welded or watertight seams. Preserve
that limitation in the handoff. Bind the core and strips to the same actual head
assembly and recheck contact after export/reimport. Host renders use an amber
diagnostic material and leave original lashes unchanged; they establish neither
final appearance nor complete animation acceptance. Post-attachment eye
clearance, coherent skin colors, normal targets, original-lash deformation and
the sealed native GLB remain required checks in the next single native pass.

Host loading retained the source's positions, triangle indices and UVs exactly.
Corner normals differed by at most 1.23e-7 in vector length between the provided
native and host Blender versions; the inherited zero normal remained present.
This diagnostic conversion must not be presented as byte-identical normal
serialization. Original source data and prior failed assets remain preserved.
