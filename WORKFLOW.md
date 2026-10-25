<!--
SPDX-License-Identifier: GPL-3.0-or-later
SPDX-FileCopyrightText: 2026 Head Workflow contributors
-->
# Reconstruction workflow

1. **Bind and isolate.** Validate the profile and input hash. Import into a new reference scene; copy mesh and armature data into a new candidate scene. Refuse ambiguous selectors, missing controls, unsupported transforms or non-triangulated source meshes. Existing work is never used as a construction target.
2. **Classify and sample.** Build connected components for the original combined hair/eye/lash node. Apply the profile's editable masks. `head_helpers.py` supplies ray sampling, UV/material sampling, polygon clipping and corner-data preservation.
3. **Open apertures.** Clip eye polygons and a narrow fitted lip-seam polygon. Rebuild weights, UVs, shape keys, colors and split normals on clipped faces. Keep untouched faces and original vertices.
4. **Construct eyeballs.** `build_eyes.py` builds closed affine spheres and derives their visible appearance from the original eye region. It does not download a replacement eye texture.
5. **Fit and animate lids.** `fit_lids_and_blink.py` fits surrounding skin to the globe and authors four sampled closures for each eye. Lash components move coherently. Eyeballs remain stationary during blinking.
6. **Find mouth boundaries and build anatomy.** The boundary stage discovers cut loops. `build_jaw_mouth.py` creates the jaw and eye bones, redistributes lower-face weights, builds the initial lining, six upper/six lower teeth and tongue.
7. **Repair the full oral envelope.** `repair_oral_envelope.py` replaces the smaller sub-loop lining with a full aperture-envelope insert and rear cap. The consolidated runner explicitly clears stale vertex groups before rebinding the replacement mesh. This is a correction made during packaging and requires fresh Blender regression testing.
8. **Apply profile corrections.** Add the two sampled eyelid skin stitches that were necessary in the final original build. They sample the source skin material and move through the blink samples. They are built before either export, so both variants receive the same corrections.
9. **Add expression recipes.** `expressions_and_export.py` adds wide/narrow/frown controls, preserves the seven original controls, records vowel/emotion mixes and exports the integrated candidate with active-scene selection filtering.
10. **Extract the head.** `head_subset_and_export.py` normalizes to four skin influences, audits protected hair/star geometry, clones the integration rig and cuts the body geometry at the configured neck height. It exports head and integrated GLBs and Blend libraries. Both glTF selection and active-scene restrictions are required to avoid cross-scene export leakage.
11. **Verify in Blender.** Confirm closed eyeball topology, zero sampled back-head/empty mouth rays, zero exposed-globe rays at full blink and preserved protected hair. Dense eye sampling uses 7,021 frontal rays per eye for the supplied profile. Empty rays count as closure failures. Restore neutral after each test. Errors fail the run rather than relabeling its outputs as accepted.
12. **Verify the export and render.** Run the GLB structural checker, then the browser harness on that exact hash. Check finite deformed vertices, movement of every control, neutral reset and stationary globes during blink. Inspect the generated comparison sheet for visual issues that numeric checks cannot determine.

## Adapting to another head

Create a new profile from that character's observed geometry. Normalize to the documented coordinate frame; fit eye rims/spheres and the lip seam; inspect connected component IDs; fit the jaw region and internal anatomy dimensions; choose the neck cut; add local lid corrections only when measured gaps require them. Re-run all checks and inspect neutral, intermediate and combined poses. Do not transfer the original profile's component IDs or stitch coordinates blindly.

## Reversibility and provenance

The input file is read only and its hash is checked again in the final manifest. Candidate scenes and files are independent. To undo a build, close the build process or remove only its newly created output directory after retaining any evidence you need. The source mesh is not part of this repository, and no reference-model data is required at runtime.

## Testing distinction

The original session's successful head and expression sheet establish the source algorithm's observed behavior. They do not establish a clean regression pass for this refactoring. The new runner moves corrections before export, introduces an explicit profile and fresh state, and fixes oral vertex-group reuse. Record a new clean Blender run before claiming reproducible reconstruction or using its outputs as accepted production assets.
