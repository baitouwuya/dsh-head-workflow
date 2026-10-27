<!--
SPDX-License-Identifier: GPL-3.0-or-later
SPDX-FileCopyrightText: 2026 Head Workflow contributors
-->
# Head Workflow

A reusable Blender command for targeted reconstruction of a rigged character's eye and mouth anatomy, with a browser verification harness and expression-sheet renderer. GPL-3.0-or-later licensed as a combined work; source only, with compatible Three.js code and its required upstream notice retained. No model assets are included.

**Status:** version 0.1.1 reproduced the head in clean Blender 5.2 and native Tripo Lab Blender 4.2 using a renderer-only compatibility patch. The actual Lab-exported GLB passed all 37 independent WebGL2 views. Close-up mouth edges and lid creasing remain visible; see VERIFICATION.md for the exact scope and limits.

Version 0.1.4 adds the canvas driver (`driver/`) that operates a Tripo Studio canvas from outside the UI, and records the measured eyes-and-gaze limit in `docs/GAZE-LIMITS.md`: the v0.1.2 recipe delivers stationary eyeballs plus blink, and gaze is not a supported stage.

The stationary-blink development correction adds validated contour construction,
conservative measured-eye depth bounds and continuous exported-morph audits.
See [the reproduced causes](docs/STATIONARY-BLINK-DIAGNOSIS.md),
[the construction API](docs/STATIONARY-BLINK-CONSTRUCTION.md), and the
[reusable head-only Lab prompt](canvas-chain/head-eyes-blink.prompt.md).
Numerical construction checks pass on the diagnosed input; native appearance,
lash/skin attachment and export verification remain separate acceptance checks.
The subsequent [visual failure reproduction](docs/STATIONARY-BLINK-VISUAL-DIAGNOSIS.md)
adds measured source-skin boundary attachment, coherent color/normal transfer and
constrained whole-lash deformation. The direct Smart Mesh native pass rendered
successfully using the Lab's supplied Blender, but failed complete skin-boundary
attachment before a full candidate. No primary model was approved or retried.
The subsequent [exterior continuity correction](docs/EXTERIOR-SKIN-CONTINUITY.md)
was reproduced and constructed in bridged host Blender. All four boundaries pass
their whole-segment checks in host and native runs. The native follow-up stopped
at original-lash contact; final appearance/export acceptance remains incomplete.

The [visual handoff correction](docs/VISUAL-BLINK-HANDOFF.md) separates numerical
diagnostics from rendered-motion acceptance, fixes double-evaluated preview
normals, and adds native-only sealing, complete-head attachment and own-file
animation verification. Host models remain diagnosis only. A new native result
must be built by its canvas Lab, reviewed from its own motion renders, published
and selected before this stage is complete.

This is a fitted workflow, not an arbitrary-head repair service. The supplied profile targets one known input topology and coordinate frame. It includes original-character numeric measurements and two local lid corrections. Use your separately held original input GLB for an exact-profile attempt. Other heads require refitting and all checks must be rerun.

## Requirements

- Blender with its glTF importer/exporter, Python, NumPy, `mathutils`, mesh corner normals and color-attribute APIs. Verified runtimes are Blender 5.2.0 LTS with glTF I/O v5.2.39 and Blender 4.2.9 LTS with glTF I/O v4.2.83. Other versions are unverified.
- Node.js 18 or newer for the local server and tests; no npm install.
- A browser with WebGL2 for actual deformation tests and the PNG sheet.
- An external source GLB with the meshes, rig, textures and seven controls described below. No account credentials, service API, or network access is needed for a local build.

## Run

From this repository's root, with `blender`, `python` and `node` on your PATH:

```sh
python head_tool.py --input private-inputs/avatar.glb --profile profiles/original-character.json --output build --validate-only
blender --background --factory-startup --python head_tool.py -- --input private-inputs/avatar.glb --profile profiles/original-character.json --output build
node tools/verify-glb.cjs build/assets/head.glb build/assets/control_manifest.json build/evidence/glb-verification.json
node tools/review-server.cjs --assets build/assets --output review-result --port 56841
```

Open the URL printed by the review server. It renders a single expression sheet and writes the PNG, per-pose deformation results, input hashes and manifest to the new result directory. The original profile produces 37 views. STOP cancels between tiles and restores neutral. Close the server with Ctrl+C after inspection. Reloading the page into the same result directory deliberately cannot overwrite its saved evidence; use a new directory to rerun.

Add `--render` to the Blender command for source-stage review images. `--factory-startup` is recommended for reproducibility; never point Blender's save command at your input. Both output directories must be new. Partial failure outputs remain for diagnosis, and the build manifest records the error. New candidate scenes remain in memory if invoked interactively; the original active scene, selection and frame are restored.

## Inputs and parameters

The source GLB is expected to import with +X facing forward, +Z up, metric-scale coordinates, identity mesh world transforms, triangulated body and hair meshes, UVs, image-textured materials, a head bone, and the original seven morphs on both source meshes. The supplied profile's input SHA-256 is checked before scene creation.

| Profile field | Meaning |
|---|---|
| `source_sha256` | Exact input binding. Change only after fitting a new profile to that input. |
| `body_prefix`, `hair_prefix`, `head_bone` | Imported mesh selectors and head bone name. Each mesh selector must match exactly one object. |
| `eyes` | Two observed rim loops, centers, radii and affine sphere fits in Blender coordinates. |
| `lip` | Mouth lateral range and polynomial describing the lip seam. |
| `editable_eye_components`, `lash_components` | Topology-dependent connected-component IDs. These are not portable across remeshing or vertex reordering. |
| `stitches` | Per-eye local corrections: lateral position, closed height, width and height. Empty is allowed only if closure checks pass. |
| `jaw_max_degrees` | Supported command range up to 8 degrees; larger values are rejected. |
| `neck_cut_z` | Height of the head-only geometry cut. |
| `eye_texture_size`, `eye_latitudes`, `eye_longitudes` | Bounded eye image/mesh sampling resolution. |
| `lid_falloff_upper`, `lid_falloff_lower`, `lid_close_fraction` | Lid influence extent and closing seam position. |
| `oral_rim_samples`, `oral_rings`, `oral_depth` | Mouth insert sampling and depth. |
| `recipes` | Vowel/emotion mixes; original controls plus sampled blinks and jaw. |
| `render`, `viewer` | Fixed Blender and browser cameras. Blender uses Z up; glTF/browser uses Y up. |

The canonical geometric thresholds and tooth/tongue dimensions in the seven stage modules remain deliberately visible in source. They are fitted to the original scale and are not all exposed as JSON controls. A differently scaled/oriented character needs normalization and refitting; changing just the selectors is insufficient.

## Outputs

- `assets/head.glb`, `head.blend`: head-only geometry with the integration skeleton.
- `assets/character-head-integrated.glb`, `.blend`: modified full-character copy.
- `assets/control_manifest.json`, `viewer.json`: control names, recipe mixes, jaw axis and camera.
- `evidence/`: stage logs, protected-hair audit, skin-influence audit, eye topology, sampled mouth visibility and dense eye-closure checks.
- Root `manifest.json`, `sha256.txt`: input binding, result status, per-stage timing and output hashes.
- Browser result directory: `expression-overview.png`, `render-report.json`, `input-binding.json`, manifest and hashes.

`web/head-controller.js` implements independent sampled blinks and a real jaw transform. Interpolate neighboring blink samples; do not sum all four. All original and added morphs are exercised individually, then blink/jaw levels and recipes. The camera and lighting are fixed across the sheet.

## Limits

The mouth lining overlaps the skin at its interface; it is not a welded anatomical cavity. Eyelid tests are frontal samples, not a proof of watertightness or all-angle collision freedom. Four-influence normalization can change low skin weights. The brow controls may remain subtle or hidden by hair. Arbitrary maximum mixtures, extreme gaze, mobile LODs and other engines are not certified. No VRM export is implemented here.

See [WORKFLOW.md](WORKFLOW.md) for stage dependencies and [docs/TRIPO-LAB.md](docs/TRIPO-LAB.md) for the future public-repository canvas run. The operator publishes the repository; this package does not read GitHub credentials, push code or contact Tripo.

## Tests

```sh
python -m unittest discover -s tests -v
node --test tests/verify-glb.test.cjs
```

These tests catch configuration and file-format errors; they do not replace the Blender build, anatomy checks, actual browser deformation test or visual review.

The added source-only geometry regressions require NumPy in the Python test
environment. They need neither Blender nor private model assets. They cover
invalid contours, neutral projection, measured swept bounds, lash masks and
seams, and collapse between LINEAR morph knots.

